"""
The stage-change service: the only code that creates applications or writes StageChange rows.

Phase 4 adds the creation path. Advance and Back (Phase 5) and Reject, Withdraw and Reactivate
(Phase 6) join it here, so every stage change shares one set of rules and one audit trail.
"""

from typing import NamedTuple

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from candidates.models import Candidate
from jobs.models import JobOpening, JobStatus
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE, Application, Stage, StageChange

JOB_CLOSED_MESSAGE = "This job is closed and isn't accepting new applications."
CANDIDATE_ARCHIVED_MESSAGE = "This candidate is archived and can't get new applications."
STALE_MESSAGE = "This application was already updated, so nothing was changed. It's now at {stage}."
UNKNOWN_ACTION_MESSAGE = "That stage action isn't recognised."
NOT_ALLOWED_MESSAGE = "{action} isn't allowed from {stage}."
HIRED_IS_PERMANENT_MESSAGE = "Hired is permanent, so this application can't be moved."


class Action(models.TextChoices):
    ADVANCE = "advance", "Advance"
    BACK = "back", "Back"


# The stage table (PRD "Stage model and transitions"). No skipping: Hired only from Offer, Back
# never from Applied, and nothing at all from Hired, Rejected or Withdrawn.
TRANSITIONS = {
    Action.ADVANCE: {
        Stage.APPLIED: Stage.SCREENING,
        Stage.SCREENING: Stage.INTERVIEW,
        Stage.INTERVIEW: Stage.FINAL_REVIEW,
        Stage.FINAL_REVIEW: Stage.OFFER,
        Stage.OFFER: Stage.HIRED,
    },
    Action.BACK: {
        Stage.SCREENING: Stage.APPLIED,
        Stage.INTERVIEW: Stage.SCREENING,
        Stage.FINAL_REVIEW: Stage.INTERVIEW,
        Stage.OFFER: Stage.FINAL_REVIEW,
    },
}


class Move(NamedTuple):
    action: Action
    target: Stage


def available_moves(stage):
    """The moves allowed from `stage`, in the order the card shows them."""
    return [
        Move(action, targets[stage]) for action, targets in TRANSITIONS.items() if stage in targets
    ]


class StageChangeRefused(Exception):
    """A request the rules don't allow. The message says why; nothing has been written."""


def create_application(*, candidate, job_opening, created_by, notes=""):
    """
    Create an application at Applied together with its creation entry (no stage → Applied).

    The guards re-read the job and candidate from the database, so a page loaded before the job
    closed or the candidate was archived can't slip through. Refusals raise StageChangeRefused.
    """
    try:
        with transaction.atomic():
            job_opening = JobOpening.objects.get(pk=job_opening.pk)
            candidate = Candidate.objects.get(pk=candidate.pk)
            if job_opening.status != JobStatus.OPEN:
                raise StageChangeRefused(JOB_CLOSED_MESSAGE)
            if candidate.archived_at is not None:
                raise StageChangeRefused(CANDIDATE_ARCHIVED_MESSAGE)
            if Application.objects.filter(candidate=candidate, job_opening=job_opening).exists():
                raise StageChangeRefused(DUPLICATE_APPLICATION_MESSAGE)

            now = timezone.now()
            application = Application.objects.create(
                candidate=candidate,
                job_opening=job_opening,
                created_by=created_by,
                stage=Stage.APPLIED,
                stage_changed_at=now,
                notes=notes,
            )
            StageChange.objects.create(
                application=application,
                from_stage=None,
                to_stage=Stage.APPLIED,
                changed_by=created_by,
                changed_at=now,
            )
    except IntegrityError:
        # Two requests for the same pair at once: both checks passed, the unique constraint
        # refused the second insert, and the transaction rolled back.
        if Application.objects.filter(candidate=candidate, job_opening=job_opening).exists():
            raise StageChangeRefused(DUPLICATE_APPLICATION_MESSAGE) from None
        raise
    return application


def current_stage(application_pk):
    return Application.objects.filter(pk=application_pk).values_list("stage", flat=True).get()


def change_stage(*, application, action, expected_stage, changed_by, note=""):
    """
    Move an application one step, as seen by a screen that showed it at `expected_stage`.

    Checks, in order: (1) the screen isn't stale, (2) the action is allowed from the current
    stage. (Phase 6 adds the required note and the archived-candidate guard.) The write is a
    conditional UPDATE … WHERE stage = expected, so if two requests race (or a button is
    double-clicked) only one can update the row, and only that one writes a StageChange.
    Refreshes `application` in place and returns the StageChange written for this move;
    refusals raise StageChangeRefused and write nothing.
    """
    with transaction.atomic():
        stage = current_stage(application.pk)
        if expected_stage != stage:
            raise StageChangeRefused(STALE_MESSAGE.format(stage=Stage(stage).label))
        if action not in Action.values:
            raise StageChangeRefused(UNKNOWN_ACTION_MESSAGE)
        action = Action(action)
        target = TRANSITIONS[action].get(stage)
        if target is None:
            if stage == Stage.HIRED:
                raise StageChangeRefused(HIRED_IS_PERMANENT_MESSAGE)
            raise StageChangeRefused(
                NOT_ALLOWED_MESSAGE.format(action=action.label, stage=Stage(stage).label)
            )

        now = timezone.now()
        updated = Application.objects.filter(pk=application.pk, stage=expected_stage).update(
            stage=target, stage_changed_at=now
        )
        if updated != 1:
            # Another request moved it between the read above and this UPDATE.
            raise StageChangeRefused(
                STALE_MESSAGE.format(stage=Stage(current_stage(application.pk)).label)
            )
        change = StageChange.objects.create(
            application_id=application.pk,
            from_stage=expected_stage,
            to_stage=target,
            changed_by=changed_by,
            changed_at=now,
            note=note.strip(),
        )
    application.refresh_from_db()
    return change
