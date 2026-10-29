"""Phase 10: Admin permanent delete of a candidate (US 17, 18; AC10)."""

from unittest import mock

from django.contrib.auth.models import Permission
from django.db.models.deletion import Collector
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from candidates.models import Candidate
from candidates.services import archive_candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.tests.utils import make_job
from pipeline.models import Application, Stage, StageChange
from pipeline.services import create_application
from pipeline.tests.utils import make_application

LIST_URL = reverse("candidates:candidate_list")


def delete_url(candidate):
    return reverse("candidates:candidate_delete", args=[candidate.pk])


class CandidateDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())
        self.candidate = make_candidate()

    def test_get_shows_a_confirmation_page_and_deletes_nothing(self):
        response = self.client.get(delete_url(self.candidate))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/confirm_delete.html")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Delete Ann Lee?</h1>")
        self.assertContains(response, "can&#x27;t be undone")
        self.assertContains(response, f'<form method="post" action="{delete_url(self.candidate)}"')
        self.assertContains(response, ">Delete candidate</button>")
        self.assertContains(response, f'href="{self.candidate.get_absolute_url()}"')  # Cancel
        self.assertTrue(Candidate.objects.exists())

    def test_admin_deletes_a_candidate_with_no_applications(self):
        response = self.client.post(delete_url(self.candidate), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Candidate Ann Lee deleted.")
        self.assertFalse(Candidate.objects.exists())

    def test_an_archived_candidate_with_no_applications_can_be_deleted(self):
        archive_candidate(self.candidate)
        self.client.post(delete_url(self.candidate))
        self.assertFalse(Candidate.objects.exists())

    def test_any_application_refuses_and_nothing_is_removed(self):
        # AC10: an active one, and a Hired one (archived candidates can only have terminal ones).
        make_application(candidate=self.candidate, job=make_job("Data Analyst"))
        make_application(candidate=self.candidate, job=make_job("Clerk"), stage=Stage.HIRED)
        before = (Application.objects.count(), StageChange.objects.count())
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(delete_url(self.candidate))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "Ann Lee can&#x27;t be deleted because they have 2 applications. "
                    "Archive the candidate instead; their hiring history is kept.",
                )
                self.assertContains(response, 'role="alert"')
                self.assertNotContains(response, ">Delete candidate</button>")
        self.assertTrue(Candidate.objects.exists())
        self.assertEqual((Application.objects.count(), StageChange.objects.count()), before)

    def test_a_stale_delete_of_an_already_deleted_candidate(self):
        stale = Candidate.objects.get()
        Candidate.objects.all().delete()  # another Admin deleted it after this page loaded
        with mock.patch("candidates.views.CandidateDeleteView.get_object", return_value=stale):
            response = self.client.post(delete_url(self.candidate), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Ann Lee was already deleted.")

    def test_unknown_candidate_is_404(self):
        self.assertEqual(self.client.get("/candidates/999999/delete/").status_code, 404)
        self.assertEqual(self.client.post("/candidates/999999/delete/").status_code, 404)


class CandidateDeletePermissionTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate()

    def test_recruiter_and_view_only_users_get_403_on_get_and_post(self):
        # AC2
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_candidate"))
        for user in (make_recruiter(), viewer):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(delete_url(self.candidate)).status_code, 403)
                self.assertEqual(self.client.post(delete_url(self.candidate)).status_code, 403)
        self.assertTrue(Candidate.objects.exists())

    def test_anonymous_post_is_redirected_to_login(self):
        response = self.client.post(delete_url(self.candidate))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertTrue(Candidate.objects.exists())

    def test_delete_button_only_for_admins_and_only_when_possible(self):
        with_application = make_candidate("busy@example.com")
        make_application(candidate=with_application)
        self.client.force_login(make_admin())
        self.assertContains(
            self.client.get(self.candidate.get_absolute_url()), delete_url(self.candidate)
        )
        self.assertNotContains(
            self.client.get(with_application.get_absolute_url()), delete_url(with_application)
        )
        self.client.force_login(make_recruiter())
        self.assertNotContains(
            self.client.get(self.candidate.get_absolute_url()), delete_url(self.candidate)
        )


def collect_without_seeing_applications(collector, objs, *args, **kwargs):
    """Collector.collect without the PROTECT lookup, as if it ran just before another request
    committed a new application for the candidate."""
    collector.add(objs)


class CandidateDeleteRaceTests(TransactionTestCase):
    """Commits for real, so SQLite's deferred foreign-key check runs."""

    serialized_rollback = True  # restore the migration-created role groups afterwards

    def test_an_application_committed_after_the_check_still_blocks_the_delete(self):
        candidate = make_candidate()
        admin = make_admin()
        create_application(candidate=candidate, job_opening=make_job(), created_by=admin)
        self.client.force_login(admin)
        with mock.patch.object(Collector, "collect", collect_without_seeing_applications):
            response = self.client.post(delete_url(candidate))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "can&#x27;t be deleted because they have 1 application.")
        self.assertTrue(Candidate.objects.filter(pk=candidate.pk).exists())
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(StageChange.objects.count(), 1)
