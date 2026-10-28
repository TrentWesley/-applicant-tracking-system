"""
The stage-change service: the only code that creates applications or writes StageChange rows.

Phase 4 adds the creation path. Advance and Back (Phase 5) and Reject, Withdraw and Reactivate
(Phase 6) join it here, so every stage change shares one set of rules and one audit trail.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from candidates.models import Candidate
from jobs.models import JobOpening, JobStatus
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE, Application, Stage, StageChange

JOB_CLOSED_MESSAGE = "This job is closed and isn't accepting new applications."
CANDIDATE_ARCHIVED_MESSAGE = "This candidate is archived and can't get new applications."


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
