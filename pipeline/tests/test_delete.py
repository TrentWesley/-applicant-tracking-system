"""Phase 10: Admin permanent delete of a never-moved application (US 47, 48; AC31)."""

import importlib
from contextlib import contextmanager
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.models import JobOpening, JobStatus
from pipeline.models import Application, Stage, StageChange
from pipeline.services import change_stage
from pipeline.tests.utils import make_application

LIST_URL = reverse("pipeline:application_list")
MOVED = (
    "This application can&#x27;t be deleted because it has moved from Applied. Only an "
    "application that never moved can be deleted, so stage history is never erased."
)
HISTORY_GUARD = "Stage history is kept"


def delete_url(application):
    return reverse("pipeline:application_delete", args=[application.pk])


def move(application, action, note=""):
    change_stage(
        application=application,
        action=action,
        expected_stage=application.stage,
        changed_by=application.created_by,
        note=note,
    )


def history(application):
    return list(
        StageChange.objects.filter(application_id=application.pk).values_list(
            "pk", "from_stage", "to_stage", "note"
        )
    )


class ApplicationDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())
        self.application = make_application()

    def test_get_shows_a_confirmation_page_and_deletes_nothing(self):
        response = self.client.get(delete_url(self.application))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/confirm_delete.html")
        self.assertContains(response, f"Delete {self.application}?</h1>")
        self.assertContains(response, "creation entry")
        self.assertContains(response, ">Delete application</button>")
        self.assertContains(response, f'href="{self.application.get_absolute_url()}"')
        self.assertTrue(Application.objects.exists())

    def test_admin_deletes_a_never_moved_application_and_its_creation_entry(self):
        # AC31. Also allowed on a closed job.
        JobOpening.objects.filter(pk=self.application.job_opening_id).update(
            status=JobStatus.CLOSED
        )
        name = str(self.application)
        response = self.client.post(delete_url(self.application), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, f"Application {name} deleted.")
        self.assertFalse(Application.objects.exists())
        self.assertFalse(StageChange.objects.exists())

    def test_an_application_that_moved_and_came_back_to_applied_is_refused(self):
        move(self.application, "advance")
        move(self.application, "back")
        self.assert_refused()

    def test_terminal_applications_are_refused(self):
        for actions in (["reject"], ["withdraw"], ["advance"] * 5):
            with self.subTest(actions=actions):
                self.application = make_application()
                for action in actions:
                    move(self.application, action, "Because.")
                self.assert_refused()

    def assert_refused(self):
        before = (self.application.stage, history(self.application))
        for method in ("get", "post"):
            response = getattr(self.client, method)(delete_url(self.application))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, MOVED)
            self.assertContains(response, 'role="alert"')
            self.assertNotContains(response, ">Delete application</button>")
        stored = Application.objects.get(pk=self.application.pk)
        self.assertEqual((stored.stage, history(stored)), before)

    def test_a_stale_delete_of_an_already_deleted_application(self):
        stale = Application.objects.get()
        name = str(stale)
        with connection.cursor() as cursor:  # another Admin deleted it after this page loaded
            cursor.execute("DELETE FROM pipeline_stagechange")
            cursor.execute("DELETE FROM pipeline_application")
        with mock.patch("pipeline.views.ApplicationDeleteView.get_object", return_value=stale):
            response = self.client.post(delete_url(self.application), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, f"{name} was already deleted.")

    def test_after_deletion_the_old_pages_and_actions_are_404(self):
        url = self.application.get_absolute_url()
        transition = reverse("pipeline:application_transition", args=[self.application.pk])
        notes = reverse("pipeline:application_notes", args=[self.application.pk])
        self.client.post(delete_url(self.application))
        self.assertEqual(self.client.get(url).status_code, 404)
        data = {"action": "advance", "expected_stage": "applied"}
        self.assertEqual(self.client.post(transition, data).status_code, 404)
        self.assertEqual(self.client.post(notes, {"notes": "x"}).status_code, 404)

    def test_unknown_application_is_404(self):
        self.assertEqual(self.client.get("/applications/999999/delete/").status_code, 404)
        self.assertEqual(self.client.post("/applications/999999/delete/").status_code, 404)


class ApplicationDeletePermissionTests(TestCase):
    def setUp(self):
        self.application = make_application()

    def test_recruiter_gets_403_on_get_and_post_and_nothing_is_removed(self):
        # AC2, AC31: Recruiters can never delete applications.
        self.client.force_login(make_recruiter())
        self.assertEqual(self.client.get(delete_url(self.application)).status_code, 403)
        self.assertEqual(self.client.post(delete_url(self.application)).status_code, 403)
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(StageChange.objects.count(), 1)

    def test_delete_button_only_for_admins_and_only_for_never_moved_applications(self):
        moved = make_application()
        move(moved, "advance")
        self.client.force_login(make_admin())
        response = self.client.get(self.application.get_absolute_url())
        self.assertContains(response, delete_url(self.application))
        self.assertNotContains(self.client.get(moved.get_absolute_url()), delete_url(moved))
        self.client.force_login(make_recruiter())
        response = self.client.get(self.application.get_absolute_url())
        self.assertNotContains(response, delete_url(self.application))


class HistoryDeleteGuardTests(TestCase):
    """
    The database keeps stage history: only the creation entry of an application still at
    Applied can be deleted (with its application). Writes that skip the service are refused too.
    """

    def test_deleting_a_moved_application_through_the_orm_is_refused(self):
        application = make_application()
        move(application, "advance")
        move(application, "back")
        before = history(application)
        with self.assertRaisesMessage(IntegrityError, HISTORY_GUARD), transaction.atomic():
            Application.objects.get(pk=application.pk).delete()
        self.assertEqual(history(application), before)

    def test_deleting_a_single_history_row_is_refused(self):
        application = make_application()
        move(application, "advance")
        with (
            self.assertRaisesMessage(IntegrityError, HISTORY_GUARD),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "DELETE FROM pipeline_stagechange "
                "WHERE application_id = %s AND from_stage IS NOT NULL",
                [application.pk],
            )
        self.assertEqual(StageChange.objects.count(), 2)

    def test_a_never_moved_application_deletes_with_its_creation_entry(self):
        Application.objects.get(pk=make_application().pk).delete()
        self.assertFalse(StageChange.objects.exists())


guards = importlib.import_module("candidates.tests.test_archive_guards")


@contextmanager
def stale_first_check(target, stale_value):
    with guards.stale_first_check(target, stale_value):
        yield


class ApplicationDeleteRaceTests(TestCase):
    def test_an_advance_committed_after_the_check_still_blocks_the_delete(self):
        # The delete's eligibility check read "never moved" just before another request's
        # Advance committed; the database guard refuses erasing that history.
        application = make_application()
        move(application, "advance")
        before = history(application)
        self.client.force_login(make_admin())
        with stale_first_check("pipeline.services.application_deletion_blocker", None):
            response = self.client.post(delete_url(application))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, MOVED)
        stored = Application.objects.get(pk=application.pk)
        self.assertEqual(stored.stage, Stage.SCREENING)
        self.assertEqual(history(stored), before)


def guard_trigger_exists():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'trigger' "
            "AND name = 'pipeline_stagechange_delete_guard'"
        )
        return cursor.fetchone() is not None


class FlushTests(TransactionTestCase):
    """
    Regression: Django's flush (and TransactionTestCase teardown, which calls it) must still
    empty a database holding moved history. Flush deletes tables in set order, which varies
    between runs, so both orders are forced here; the trigger must be back afterwards.
    """

    serialized_rollback = True

    def make_moved_history(self):
        application = make_application(created_by=make_user("flush-creator"))
        move(application, "advance")
        move(application, "reject", "No.")

    def test_flush_works_in_either_table_order_and_restores_the_guard(self):
        real = connection.introspection.django_table_names
        for first in ("pipeline_stagechange", "pipeline_application"):
            with self.subTest(first=first):
                self.make_moved_history()

                def ordered(*args, first=first, **kwargs):
                    return sorted(real(*args, **kwargs), key=lambda table: table != first)

                with mock.patch.object(connection.introspection, "django_table_names", ordered):
                    call_command("flush", verbosity=0, interactive=False)
                self.assertFalse(StageChange.objects.exists())
                self.assertFalse(Application.objects.exists())
                self.assertTrue(guard_trigger_exists())

    def test_teardown_flush_succeeds_with_moved_history_in_the_database(self):
        self.make_moved_history()
        self.assertEqual(StageChange.objects.count(), 3)
        # The test passes only if the flush after it succeeds.


class StrictHistoryGuardTests(TestCase):
    def test_history_cannot_be_deleted_once_its_application_row_is_gone(self):
        # Raw SQL that deletes the application first (foreign keys are only checked at commit)
        # still can't remove its history, so the transaction can never commit.
        for moved in (True, False):
            with self.subTest(moved=moved):
                application = make_application()
                if moved:
                    move(application, "advance")
                with (
                    self.assertRaisesMessage(IntegrityError, HISTORY_GUARD),
                    transaction.atomic(),
                    connection.cursor() as cursor,
                ):
                    cursor.execute(
                        "DELETE FROM pipeline_application WHERE id = %s", [application.pk]
                    )
                    cursor.execute(
                        "DELETE FROM pipeline_stagechange WHERE application_id = %s",
                        [application.pk],
                    )
                self.assertTrue(Application.objects.filter(pk=application.pk).exists())


class FullAc31RuleTests(TestCase):
    """Final review: the trigger itself holds every part of AC31, not just the service."""

    def test_an_applied_application_with_more_than_one_entry_is_refused(self):
        # Only raw SQL can give a never-moved application a second creation-style entry, but the
        # rule is "exactly one StageChange", so the database must refuse deleting it.
        application = make_application()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO pipeline_stagechange "
                "(application_id, from_stage, to_stage, changed_by_id, changed_at, note) "
                "SELECT application_id, NULL, 'applied', changed_by_id, changed_at, '' "
                "FROM pipeline_stagechange WHERE application_id = %s",
                [application.pk],
            )
        with self.assertRaisesMessage(IntegrityError, HISTORY_GUARD), transaction.atomic():
            Application.objects.get(pk=application.pk).delete()
        self.assertEqual(StageChange.objects.filter(application_id=application.pk).count(), 2)


class OrmDeletionPathsTests(TestCase):
    """
    Every Django ORM path that could delete stage history. (Also covered elsewhere: an
    instance's or queryset's own delete() raises HistoryIsImmutable, and PROTECT stops deleting
    the candidate, job or user an application or history entry points to; see
    pipeline/tests/test_models.py.)
    """

    def setUp(self):
        self.never_moved = make_application()
        self.moved = make_application()
        move(self.moved, "advance")

    def test_queryset_delete_of_a_moved_application_is_refused(self):
        with self.assertRaisesMessage(IntegrityError, HISTORY_GUARD), transaction.atomic():
            Application.objects.filter(pk=self.moved.pk).delete()
        self.assertEqual(history(self.moved)[-1][2], Stage.SCREENING)

    def test_a_bulk_delete_that_includes_a_moved_application_removes_nothing(self):
        with self.assertRaisesMessage(IntegrityError, HISTORY_GUARD), transaction.atomic():
            Application.objects.all().delete()
        self.assertEqual(Application.objects.count(), 2)
        self.assertEqual(StageChange.objects.count(), 3)

    def test_a_bulk_delete_of_only_never_moved_applications_is_allowed(self):
        Application.objects.filter(pk=self.never_moved.pk).delete()
        self.assertFalse(Application.objects.filter(pk=self.never_moved.pk).exists())
        self.assertEqual(StageChange.objects.count(), 2)


class InFlightRequestOnADeletedApplicationTests(TestCase):
    """Final review: a stage move whose request loaded the application just before an Admin
    deleted it gets a 404, not a server error."""

    def test_a_transition_in_flight_when_the_application_is_deleted(self):
        application = make_application()
        stale = Application.objects.get(pk=application.pk)
        self.client.force_login(make_admin())
        self.client.post(delete_url(application))
        self.assertFalse(Application.objects.exists())
        url = reverse("pipeline:application_transition", args=[stale.pk])
        data = {"action": "advance", "expected_stage": "applied"}
        for headers in ({}, {"HTTP_HX_REQUEST": "true"}):
            with self.subTest(htmx=bool(headers)):
                with mock.patch("pipeline.views.get_object_or_404", return_value=stale):
                    response = self.client.post(url, data, **headers)
                self.assertEqual(response.status_code, 404)
        self.assertFalse(StageChange.objects.exists())

    def test_a_notes_save_in_flight_when_the_application_is_deleted(self):
        application = make_application(notes="Before.")
        stale = Application.objects.get(pk=application.pk)
        self.client.force_login(make_admin())
        self.client.post(delete_url(application))
        self.assertFalse(Application.objects.exists())
        url = reverse("pipeline:application_notes", args=[stale.pk])
        for headers in ({}, {"HTTP_HX_REQUEST": "true"}):
            with self.subTest(htmx=bool(headers)):
                with mock.patch(
                    "pipeline.views.ApplicationNotesView.get_object", return_value=stale
                ):
                    response = self.client.post(url, {"notes": "Edited."}, **headers)
                self.assertEqual(response.status_code, 404)
        # Neither request recreated the application or wrote any history.
        self.assertFalse(Application.objects.exists())
        self.assertFalse(StageChange.objects.exists())
        # The database is still usable: no broken transaction left behind.
        self.assertEqual(make_application().stage_changes.count(), 1)
