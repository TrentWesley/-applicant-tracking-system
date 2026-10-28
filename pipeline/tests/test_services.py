from unittest import mock

from django.db import DatabaseError, transaction
from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils import timezone

from candidates.tests.utils import make_candidate
from core.tests.utils import make_recruiter
from jobs.models import JobStatus
from jobs.tests.utils import make_job
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE, Application, Stage, StageChange
from pipeline.services import (
    CANDIDATE_ARCHIVED_MESSAGE,
    JOB_CLOSED_MESSAGE,
    StageChangeRefused,
    create_application,
)


class CreateApplicationTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate()
        self.job = make_job()
        self.user = make_recruiter()

    def create(self, **extra):
        fields = {"candidate": self.candidate, "job_opening": self.job, "created_by": self.user}
        return create_application(**fields | extra)

    def assert_nothing_written(self):
        self.assertFalse(Application.objects.exists())
        self.assertFalse(StageChange.objects.exists())

    def test_new_application_starts_at_applied_with_one_creation_entry(self):
        application = self.create(notes="Met at the career fair.")
        self.assertEqual(application.stage, Stage.APPLIED)
        self.assertEqual(application.created_by, self.user)
        self.assertEqual(application.notes, "Met at the career fair.")
        entry = application.stage_changes.get()
        self.assertIsNone(entry.from_stage)
        self.assertEqual(entry.to_stage, Stage.APPLIED)
        self.assertEqual(entry.changed_by, self.user)
        self.assertEqual(entry.note, "")

    def test_stage_changed_at_matches_the_creation_entry(self):
        application = self.create()
        self.assertEqual(application.stage_changed_at, application.stage_changes.get().changed_at)

    def test_application_and_entry_are_written_in_one_transaction(self):
        with mock.patch.object(transaction, "atomic", wraps=transaction.atomic) as atomic:
            self.create()
        atomic.assert_called_once()

    def test_if_the_history_write_fails_no_application_is_left_behind(self):
        with (
            mock.patch.object(StageChange.objects, "create", side_effect=DatabaseError("disk")),
            self.assertRaises(DatabaseError),
        ):
            self.create()
        self.assert_nothing_written()

    def test_closed_job_is_refused_and_nothing_is_written(self):
        self.job.status = JobStatus.CLOSED
        self.job.save()
        with self.assertRaisesMessage(StageChangeRefused, JOB_CLOSED_MESSAGE):
            self.create()
        self.assert_nothing_written()

    def test_archived_candidate_is_refused_and_nothing_is_written(self):
        self.candidate.archived_at = timezone.now()
        self.candidate.save()
        with self.assertRaisesMessage(StageChangeRefused, CANDIDATE_ARCHIVED_MESSAGE):
            self.create()
        self.assert_nothing_written()

    def test_guards_read_the_database_not_the_objects_passed_in(self):
        # Another request closed the job after this one loaded it.
        type(self.job).objects.filter(pk=self.job.pk).update(status=JobStatus.CLOSED)
        self.assertEqual(self.job.status, JobStatus.OPEN)
        with self.assertRaisesMessage(StageChangeRefused, JOB_CLOSED_MESSAGE):
            self.create()
        self.assert_nothing_written()

    def test_duplicate_pair_is_refused_and_writes_nothing_more(self):
        self.create()
        with self.assertRaisesMessage(StageChangeRefused, DUPLICATE_APPLICATION_MESSAGE):
            self.create(created_by=make_recruiter("other"))
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(StageChange.objects.count(), 1)

    def test_duplicate_that_slips_past_the_check_is_still_refused_by_the_database(self):
        # Two requests for the same pair at the same instant: both checks pass, one insert fails.
        self.create()
        with (
            # The pre-check misses the other request's row; the re-check after the failed insert
            # sees it.
            mock.patch.object(QuerySet, "exists", side_effect=[False, True]),
            self.assertRaisesMessage(StageChangeRefused, DUPLICATE_APPLICATION_MESSAGE),
        ):
            self.create(created_by=make_recruiter("other"))
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(StageChange.objects.count(), 1)

    def test_the_same_candidate_can_apply_to_another_open_job(self):
        self.create()
        self.create(job_opening=make_job("Engineer"))
        self.assertEqual(self.candidate.applications.count(), 2)
