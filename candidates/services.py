"""
Archive and Restore: the only ways a candidate's archived state changes. Neither touches any
application or stage history.

The rule "an archived candidate never has an active application" is held by the database, not
just these checks (see pipeline/migrations/0004_archived_candidate_guards.py):

- SQLite triggers refuse inserting an application for an archived candidate, moving one of their
  applications into an active stage, and archiving a candidate who has an active application.
  A trigger runs inside the writing statement, and SQLite has a single writer, so it always
  sees the latest committed rows: of an archive and a concurrent create (or Reactivate), the
  second write is refused, whichever order the requests' checks ran in.
- `transaction_mode = "IMMEDIATE"` (config/settings.py) makes every transaction take that write
  lock at BEGIN. A second request then waits for the first to commit and its checks see the
  result, so it gets the normal refusal message instead of a "database is locked" error.

The checks below give the friendly message; a trigger refusal (ARCHIVED_GUARD in the error) is
turned into the same message.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from candidates.models import Candidate
from pipeline.models import ACTIVE_STAGES, Application

ARCHIVED_GUARD = "archived-candidate guard"  # starts every trigger message in pipeline/0004
ARCHIVE_ACTIVE_MESSAGE = (
    "{candidate} can't be archived while they have active applications: {applications}. "
    "Move each one to Hired, Rejected or Withdrawn first."
)
ALREADY_ARCHIVED_MESSAGE = "This candidate is already archived, so nothing was changed."
ALREADY_ACTIVE_MESSAGE = "This candidate is already active, so nothing was changed."


class CandidateStatusRefused(Exception):
    """An Archive or Restore that changed nothing. `applications` lists any active ones."""

    def __init__(self, message, applications=()):
        super().__init__(message)
        self.applications = list(applications)


def is_archived_guard_error(error):
    return ARCHIVED_GUARD in str(error)


def candidate_is_archived(candidate_pk):
    return Candidate.objects.filter(pk=candidate_pk, archived_at__isnull=False).exists()


def active_applications(candidate):
    return list(
        Application.objects.filter(candidate=candidate, stage__in=ACTIVE_STAGES)
        .select_related("job_opening")
        .order_by("pk")
    )


def _active_refusal(candidate, applications):
    listed = ", ".join(f"{a.job_opening} ({a.get_stage_display()})" for a in applications)
    message = ARCHIVE_ACTIVE_MESSAGE.format(candidate=candidate, applications=listed)
    return CandidateStatusRefused(message, applications)


def archive_candidate(candidate):
    """Archive a candidate with no active applications. Refreshes `candidate` in place."""
    try:
        with transaction.atomic():
            active = active_applications(candidate)
            if active:
                raise _active_refusal(candidate, active)
            now = timezone.now()
            updated = Candidate.objects.filter(pk=candidate.pk, archived_at__isnull=True).update(
                archived_at=now, updated_at=now
            )
    except IntegrityError as error:
        if not is_archived_guard_error(error):
            raise
        # An application was created after the check above; the database refused the archive.
        raise _active_refusal(candidate, active_applications(candidate)) from None
    candidate.refresh_from_db()
    if updated != 1:
        raise CandidateStatusRefused(ALREADY_ARCHIVED_MESSAGE)


def restore_candidate(candidate):
    """Make an archived candidate active again. Refreshes `candidate` in place."""
    now = timezone.now()
    updated = Candidate.objects.filter(pk=candidate.pk, archived_at__isnull=False).update(
        archived_at=None, updated_at=now
    )
    candidate.refresh_from_db()
    if updated != 1:
        raise CandidateStatusRefused(ALREADY_ACTIVE_MESSAGE)
