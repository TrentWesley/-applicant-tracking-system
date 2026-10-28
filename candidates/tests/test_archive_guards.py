"""
The archived-candidate invariant, enforced by the database: an archived candidate never has an
active application. The interleaving tests below reproduce the race window by letting a
service's check pass (as if it read just before another request committed), then committing
that other request's write before the service writes. Only the database guard can refuse then.
"""

import importlib
from contextlib import contextmanager
from unittest import mock

from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from candidates.services import (
    ARCHIVED_GUARD,
    CandidateStatusRefused,
    archive_candidate,
)
from candidates.tests.utils import make_candidate
from core.tests.utils import make_recruiter
from jobs.tests.utils import make_job
from pipeline.models import ACTIVE_STAGES, Application, Stage, StageChange
from pipeline.services import (
    CANDIDATE_ARCHIVED_MESSAGE,
    StageChangeRefused,
    change_stage,
    create_application,
)
from pipeline.tests.utils import make_application

guard_migration = importlib.import_module("pipeline.migrations.0004_archived_candidate_guards")


def archive_directly(candidate):
    """Another request's archive, committed without going through this request's checks."""
    Candidate.objects.filter(pk=candidate.pk).update(archived_at=timezone.now())


@contextmanager
def stale_first_check(target, stale_value):
    """Make the service's first call to `target` return what it read before the other
    request committed; later calls (such as re-reading for a message) see the real data."""
    module_name, name = target.rsplit(".", 1)
    real = getattr(importlib.import_module(module_name), name)
    calls = []

    def check(*args, **kwargs):
        calls.append(args)
        return stale_value if len(calls) == 1 else real(*args, **kwargs)

    with mock.patch(target, check):
        yield


class DatabaseGuardTests(TestCase):
    """Writes that skip the services entirely are still refused by the SQLite triggers."""

    def setUp(self):
        self.candidate = make_candidate()

    def test_inserting_an_application_for_an_archived_candidate(self):
        archive_directly(self.candidate)
        with self.assertRaisesMessage(IntegrityError, ARCHIVED_GUARD), transaction.atomic():
            Application.objects.create(
                candidate=self.candidate,
                job_opening=make_job(),
                created_by=make_recruiter(),
                stage_changed_at=timezone.now(),
            )
        self.assertFalse(Application.objects.exists())

    def test_moving_an_archived_candidates_application_into_an_active_stage(self):
        application = make_application(candidate=self.candidate, stage=Stage.REJECTED)
        archive_directly(self.candidate)
        for stage in ACTIVE_STAGES:
            with self.subTest(stage=stage):
                with (
                    self.assertRaisesMessage(IntegrityError, ARCHIVED_GUARD),
                    transaction.atomic(),
                ):
                    Application.objects.filter(pk=application.pk).update(stage=stage)
                self.assertEqual(Application.objects.get().stage, Stage.REJECTED)

    def test_terminal_moves_are_still_allowed_for_an_archived_candidate(self):
        application = make_application(candidate=self.candidate, stage=Stage.REJECTED)
        archive_directly(self.candidate)
        Application.objects.filter(pk=application.pk).update(stage=Stage.WITHDRAWN)
        self.assertEqual(Application.objects.get().stage, Stage.WITHDRAWN)

    def test_archiving_a_candidate_with_an_active_application(self):
        make_application(candidate=self.candidate, stage=Stage.OFFER)
        with self.assertRaisesMessage(IntegrityError, ARCHIVED_GUARD), transaction.atomic():
            archive_directly(self.candidate)
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_other_candidate_writes_are_unaffected(self):
        make_application(candidate=self.candidate, stage=Stage.OFFER)
        Candidate.objects.filter(pk=self.candidate.pk).update(notes="Strong SQL.")
        self.candidate.refresh_from_db()
        self.candidate.phone = "806-555-0100"
        self.candidate.save()
        self.assertEqual(Candidate.objects.get().notes, "Strong SQL.")

    def test_the_trigger_stage_list_matches_the_active_stages(self):
        self.assertEqual(set(guard_migration.ACTIVE_STAGE_VALUES), {s.value for s in ACTIVE_STAGES})


class InterleavedRequestTests(TestCase):
    """
    Each test commits the other request's write first, then lets the service's first check
    return what it would have read just before that commit. The service's own write must then
    be refused by the database guard, with the normal message and nothing written.
    """

    def setUp(self):
        self.recruiter = make_recruiter()
        self.candidate = make_candidate()

    def test_create_whose_check_ran_before_an_archive_committed(self):
        archive_directly(self.candidate)
        with (
            stale_first_check("pipeline.services.candidate_is_archived", False),
            self.assertRaisesMessage(StageChangeRefused, CANDIDATE_ARCHIVED_MESSAGE),
        ):
            create_application(
                candidate=self.candidate, job_opening=make_job(), created_by=self.recruiter
            )
        self.assertFalse(Application.objects.exists())
        self.assertFalse(StageChange.objects.exists())

    def test_archive_whose_check_ran_before_a_create_committed(self):
        create_application(
            candidate=self.candidate, job_opening=make_job("Late Job"), created_by=self.recruiter
        )
        with (
            stale_first_check("candidates.services.active_applications", []),
            self.assertRaises(CandidateStatusRefused) as refusal,
        ):
            archive_candidate(self.candidate)
        # The refusal re-reads the applications, so it names the one that slipped in.
        self.assertIn("active applications: Late Job (Applied).", str(refusal.exception))
        self.assertIsNone(Candidate.objects.get().archived_at)
        self.assertEqual(Application.objects.get().stage, Stage.APPLIED)

    def test_reactivate_whose_check_ran_before_an_archive_committed(self):
        application = make_application(candidate=self.candidate, stage=Stage.INTERVIEW)
        change_stage(
            application=application,
            action="reject",
            expected_stage=Stage.INTERVIEW,
            changed_by=self.recruiter,
            note="No.",
        )
        archive_directly(self.candidate)
        count = StageChange.objects.count()
        with (
            stale_first_check("pipeline.services.candidate_is_archived", False),
            self.assertRaisesMessage(StageChangeRefused, "This candidate is archived"),
        ):
            change_stage(
                application=application,
                action="reactivate",
                expected_stage=Stage.REJECTED,
                changed_by=self.recruiter,
                note="Misclick.",
            )
        self.assertEqual(Application.objects.get().stage, Stage.REJECTED)
        self.assertEqual(StageChange.objects.count(), count)


class EditDoesNotOverwriteArchivedStateTests(TestCase):
    """
    Regression: the edit form saved every column from the candidate it had loaded, so an
    Archive or Restore committed between that load and the save was silently undone (or, once
    the restored candidate had a new application, the trigger refused the save with a 500).
    """

    def setUp(self):
        self.client.force_login(make_recruiter())
        self.candidate = make_candidate()

    def edit_with_object_loaded_before(self, change):
        stale = Candidate.objects.get(pk=self.candidate.pk)  # the edit request's copy
        change()  # another request's Archive or Restore commits now
        data = {
            "first_name": "Ann",
            "last_name": "Lee",
            "email": "ann.lee@example.com",
            "source": "referral",
            "phone": "806-555-0100",
        }
        with mock.patch("candidates.views.CandidateUpdateView.get_object", return_value=stale):
            return self.client.post(
                reverse("candidates:candidate_update", args=[self.candidate.pk]), data
            )

    def test_an_archive_during_an_edit_stays_archived(self):
        response = self.edit_with_object_loaded_before(lambda: archive_directly(self.candidate))
        self.assertEqual(response.status_code, 302)
        stored = Candidate.objects.get()
        self.assertEqual(stored.phone, "806-555-0100")
        self.assertIsNotNone(stored.archived_at)

    def test_a_restore_and_new_application_during_an_edit(self):
        archive_directly(self.candidate)

        def restore_and_apply():
            Candidate.objects.filter(pk=self.candidate.pk).update(archived_at=None)
            make_application(candidate=self.candidate)

        response = self.edit_with_object_loaded_before(restore_and_apply)
        self.assertEqual(response.status_code, 302)
        stored = Candidate.objects.get()
        self.assertEqual(stored.phone, "806-555-0100")
        self.assertIsNone(stored.archived_at)


class TransactionModeTests(TestCase):
    def test_sqlite_transactions_take_the_write_lock_at_begin(self):
        # Without this, two read-then-write transactions deadlock and one fails with
        # "database is locked"; with it the second waits and then sees the first's commit.
        self.assertEqual(settings.DATABASES["default"]["OPTIONS"]["transaction_mode"], "IMMEDIATE")
