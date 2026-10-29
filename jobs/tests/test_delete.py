"""Phase 10: Admin permanent delete of a job opening (US 30, 31; AC17)."""

from unittest import mock

from django.db.models.deletion import Collector
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter
from jobs.models import JobOpening, JobSkill, JobStatus, Skill
from jobs.tests.test_job_views import make_viewer
from jobs.tests.utils import make_job, make_skill
from pipeline.models import Application, Stage, StageChange
from pipeline.services import create_application
from pipeline.tests.utils import make_application

LIST_URL = reverse("jobs:job_list")


def delete_url(job):
    return reverse("jobs:job_delete", args=[job.pk])


class JobDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())
        self.python = make_skill("Python")
        self.job = make_job(skills=[self.python])

    def test_get_shows_a_confirmation_page_and_deletes_nothing(self):
        response = self.client.get(delete_url(self.job))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/confirm_delete.html")
        self.assertContains(response, "Delete Data Analyst?</h1>")
        self.assertContains(response, ">Delete job opening</button>")
        self.assertContains(response, f'href="{self.job.get_absolute_url()}"')  # Cancel
        self.assertTrue(JobOpening.objects.exists())

    def test_admin_deletes_open_and_closed_jobs_with_no_applications(self):
        # AC17. The job's skill assignments go with it; the skills themselves stay.
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        for job in (self.job, closed):
            with self.subTest(status=job.status):
                response = self.client.post(delete_url(job), follow=True)
                self.assertRedirects(response, LIST_URL)
                self.assertContains(response, f"Job opening {job} deleted.")
                self.assertFalse(JobOpening.objects.filter(pk=job.pk).exists())
        self.assertFalse(JobSkill.objects.exists())
        self.assertEqual(list(Skill.objects.all()), [self.python])

    def test_any_application_refuses_with_close_it_instead(self):
        make_application(job=self.job)
        make_application(job=self.job, stage=Stage.HIRED)
        before = (Application.objects.count(), StageChange.objects.count())
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(delete_url(self.job))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "Data Analyst can&#x27;t be deleted because it has 2 applications. "
                    "Close the job instead to stop new applications; its hiring history is kept.",
                )
                self.assertNotContains(response, ">Delete job opening</button>")
        self.assertTrue(JobOpening.objects.filter(pk=self.job.pk).exists())
        self.assertEqual(list(self.job.skills.all()), [self.python])
        self.assertEqual((Application.objects.count(), StageChange.objects.count()), before)

    def test_a_stale_delete_of_an_already_deleted_job(self):
        stale = JobOpening.objects.get()
        JobOpening.objects.all().delete()
        with mock.patch("jobs.views.JobDeleteView.get_object", return_value=stale):
            response = self.client.post(delete_url(self.job), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Data Analyst was already deleted.")

    def test_unknown_job_is_404(self):
        self.assertEqual(self.client.get("/jobs/999999/delete/").status_code, 404)
        self.assertEqual(self.client.post("/jobs/999999/delete/").status_code, 404)


class JobDeletePermissionTests(TestCase):
    def setUp(self):
        self.job = make_job()

    def test_recruiter_and_view_only_users_get_403_on_get_and_post(self):
        for user in (make_recruiter(), make_viewer()):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(delete_url(self.job)).status_code, 403)
                self.assertEqual(self.client.post(delete_url(self.job)).status_code, 403)
        self.assertTrue(JobOpening.objects.exists())

    def test_delete_button_only_for_admins_and_only_when_possible(self):
        busy = make_job("Busy Role")
        make_application(job=busy)
        self.client.force_login(make_admin())
        self.assertContains(self.client.get(self.job.get_absolute_url()), delete_url(self.job))
        self.assertNotContains(self.client.get(busy.get_absolute_url()), delete_url(busy))
        self.client.force_login(make_recruiter())
        self.assertNotContains(self.client.get(self.job.get_absolute_url()), delete_url(self.job))


def collect_without_seeing_applications(collector, objs, *args, **kwargs):
    """Collector.collect without the PROTECT lookup, as if it ran just before another request
    committed a new application to the job."""
    collector.add(objs)


class JobDeleteRaceTests(TransactionTestCase):
    """Commits for real, so SQLite's deferred foreign-key check runs."""

    serialized_rollback = True

    def test_an_application_committed_after_the_check_still_blocks_the_delete(self):
        job = make_job()
        admin = make_admin()
        create_application(candidate=make_candidate(), job_opening=job, created_by=admin)
        self.client.force_login(admin)
        with mock.patch.object(Collector, "collect", collect_without_seeing_applications):
            response = self.client.post(delete_url(job))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "can&#x27;t be deleted because it has 1 application.")
        self.assertTrue(JobOpening.objects.filter(pk=job.pk).exists())
        self.assertEqual(Application.objects.count(), 1)
