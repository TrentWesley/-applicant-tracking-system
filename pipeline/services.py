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
from pipeline.models import (
    ACTIVE_STAGES,
    DUPLICATE_APPLICATION_MESSAGE,
    Application,
    Stage,
    StageChange,
)

JOB_CLOSED_MESSAGE = "This job is closed and isn't accepting new applications."
CANDIDATE_ARCHIVED_MESSAGE = "This candidate is archived and can't get new applications."
STALE_MESSAGE = "This application was already updated, so nothing was changed. It's now at {stage}."
UNKNOWN_ACTION_MESSAGE = "That stage action isn't recognised."
NOT_ALLOWED_MESSAGE = "{action} isn't allowed from {stage}."
HIRED_IS_PERMANENT_MESSAGE = "Hired is permanent, so this application can't be moved."
NOTE_REQUIRED_MESSAGE = "A note is required to {verb}."
NO_REACTIVATION_TARGET_MESSAGE = (
    "This application's history doesn't show which stage to return to, so it can't be reactivated."
)
REACTIVATE_ARCHIVED_MESSAGE = (
    "This candidate is archived, so the application can't be reactivated. "
    "Restore the candidate first."
)


class Action(models.TextChoices):
    ADVANCE = "advance", "Advance"
    BACK = "back", "Back"
    REJECT = "reject", "Reject"
    WITHDRAW = "withdraw", "Withdraw"
    REACTIVATE = "reactivate", "Reactivate"


NOTE_REQUIRED = (Action.REJECT, Action.WITHDRAW, Action.REACTIVATE)
REACTIVATE_FROM = (Stage.REJECTED, Stage.WITHDRAWN)

# The stage table (PRD "Stage model and transitions"). No skipping: Hired only from Offer, Back
# never from Applied, and nothing at all from Hired. Reactivate isn't here because its target
# comes from the history (see reactivation_target); it's allowed only from REACTIVATE_FROM.
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
    Action.REJECT: dict.fromkeys(ACTIVE_STAGES, Stage.REJECTED),
    Action.WITHDRAW: dict.fromkeys(ACTIVE_STAGES, Stage.WITHDRAWN),
}


class Move(NamedTuple):
    action: Action
    target: Stage | None  # None only for a Reactivate whose target wasn't looked up

    @property
    def needs_note(self):
        return self.action in NOTE_REQUIRED

    @property
    def label(self):
        if self.target is None or self.action in (Action.REJECT, Action.WITHDRAW):
            return self.action.label
        return f"{self.action.label} to {self.target.label}"


def available_moves(stage, reactivate_to=None):
    """The moves allowed from `stage`, in the order the card shows them."""
    moves = [
        Move(action, targets[stage]) for action, targets in TRANSITIONS.items() if stage in targets
    ]
    if stage in REACTIVATE_FROM:
        moves.append(Move(Action.REACTIVATE, reactivate_to))
    return moves


def _reactivation_target(application_pk, stage):
    # A Rejected or Withdrawn application can only leave by reactivation, so its latest entry is
    # the move into that stage, and the entry's from-stage is where it returns.
    latest = StageChange.objects.filter(application_id=application_pk).last()
    if latest and latest.to_stage == stage and latest.from_stage in ACTIVE_STAGES:
        return Stage(latest.from_stage)
    return None


def reactivation_target(application):
    """The active stage a Rejected or Withdrawn application returns to; otherwise None."""
    if application.stage not in REACTIVATE_FROM:
        return None
    return _reactivation_target(application.pk, application.stage)


class StageChangeRefused(Exception):
    """A request the rules don't allow. The message says why; nothing has been written."""


class NoteRequired(StageChangeRefused):
    """Reject, Withdraw or Reactivate without a note, so the form can stay open for one."""


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
    stage, (3) Reject, Withdraw and Reactivate have a note after trimming, (4) Reactivate's
    candidate isn't archived. A closed job doesn't block Reactivate. The write is a
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
        if action == Action.REACTIVATE and stage in REACTIVATE_FROM:
            target = _reactivation_target(application.pk, stage)
            if target is None:
                raise StageChangeRefused(NO_REACTIVATION_TARGET_MESSAGE)
        else:
            target = TRANSITIONS.get(action, {}).get(stage)
        if target is None:
            if stage == Stage.HIRED:
                raise StageChangeRefused(HIRED_IS_PERMANENT_MESSAGE)
            raise StageChangeRefused(
                NOT_ALLOWED_MESSAGE.format(action=action.label, stage=Stage(stage).label)
            )
        note = note.strip()
        if action in NOTE_REQUIRED and not note:
            raise NoteRequired(NOTE_REQUIRED_MESSAGE.format(verb=action.label.lower()))
        archived = Candidate.objects.filter(applications=application.pk, archived_at__isnull=False)
        if action == Action.REACTIVATE and archived.exists():
            raise StageChangeRefused(REACTIVATE_ARCHIVED_MESSAGE)

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
            note=note,
        )
    application.refresh_from_db()
    return change
