"""
Close and Reopen: the only ways a job's status changes. Each changes the job's status and
nothing else; applications and their history are left alone.
"""

from django.utils import timezone

from core.deletion import delete_or_refuse
from jobs.models import JobOpening, JobStatus

ALREADY_CLOSED_MESSAGE = "This job is already closed, so nothing was changed."
ALREADY_OPEN_MESSAGE = "This job is already open, so nothing was changed."


class JobStatusUnchanged(Exception):
    """A Close of a closed job or a Reopen of an open one. The message says so."""


def _set_status(job, from_status, to_status, message):
    # Conditional UPDATE, so a double-click or a stale page changes the row at most once.
    updated = JobOpening.objects.filter(pk=job.pk, status=from_status).update(
        status=to_status, updated_at=timezone.now()
    )
    job.refresh_from_db()
    if updated != 1:
        raise JobStatusUnchanged(message)


def close_job(job):
    """Stop new applications. Refreshes `job` in place."""
    _set_status(job, JobStatus.OPEN, JobStatus.CLOSED, ALREADY_CLOSED_MESSAGE)


def reopen_job(job):
    """Accept new applications again. Refreshes `job` in place."""
    _set_status(job, JobStatus.CLOSED, JobStatus.OPEN, ALREADY_OPEN_MESSAGE)


HAS_APPLICATIONS_MESSAGE = (
    "{job} can't be deleted because it has {count} application{plural}. "
    "Close the job instead to stop new applications; its hiring history is kept."
)


def deletion_blocker(job):
    """Why `job` can't be deleted right now, or None. (Admin delete, Phase 10.)"""
    count = job.applications.count()
    if count:
        plural = "" if count == 1 else "s"
        return HAS_APPLICATIONS_MESSAGE.format(job=job, count=count, plural=plural)
    return None


def delete_job(job):
    """
    Permanently delete an Open or Closed job with no applications (Application.job_opening is
    PROTECT). Its skill assignments go with it; the skills themselves stay.
    """
    delete_or_refuse(job, lambda: deletion_blocker(job))
