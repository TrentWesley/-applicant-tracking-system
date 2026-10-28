from django.test import TestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter
from jobs.models import JobOpening, JobStatus
from jobs.services import JobStatusUnchanged, close_job, reopen_job
from jobs.tests.test_job_views import detail_url, make_viewer
from jobs.tests.utils import make_job
from pipeline.models import Application, Stage, StageChange
from pipeline.tests.utils import make_application


def close_url(job):
    return reverse("jobs:job_close", args=[job.pk])


def reopen_url(job):
    return reverse("jobs:job_reopen", args=[job.pk])


def snapshot(job):
    """Every application on the job, with its stage, stage time and history size."""
    return [
        (a.pk, a.stage, a.stage_changed_at, a.stage_changes.count())
        for a in Application.objects.filter(job_opening=job).order_by("pk")
    ]


class CloseReopenServiceTests(TestCase):
    def setUp(self):
        self.job = make_job()

    def test_close_sets_closed_and_bumps_updated_at(self):
        before = self.job.updated_at
        close_job(self.job)
        self.assertEqual(self.job.status, JobStatus.CLOSED)  # refreshed in place
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.CLOSED)
        self.assertGreater(self.job.updated_at, before)

    def test_reopen_sets_open(self):
        close_job(self.job)
        reopen_job(self.job)
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_closing_a_closed_job_is_refused_and_changes_nothing(self):
        close_job(self.job)
        updated_at = JobOpening.objects.get().updated_at
        with self.assertRaisesMessage(JobStatusUnchanged, "already closed"):
            close_job(self.job)
        self.assertEqual(JobOpening.objects.get().updated_at, updated_at)

    def test_reopening_an_open_job_is_refused(self):
        with self.assertRaisesMessage(JobStatusUnchanged, "already open"):
            reopen_job(self.job)
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_a_stale_job_object_reads_the_database(self):
        # Another request closed it after this object was loaded.
        JobOpening.objects.filter(pk=self.job.pk).update(status=JobStatus.CLOSED)
        with self.assertRaisesMessage(JobStatusUnchanged, "already closed"):
            close_job(self.job)
        self.assertEqual(self.job.status, JobStatus.CLOSED)  # refreshed even when refused

    def test_close_and_reopen_change_only_the_job(self):
        # AC12 / AC13: no application's stage, stage time or history changes.
        other_job = make_job("Data Engineer")
        for stage in (Stage.APPLIED, Stage.INTERVIEW, Stage.OFFER, Stage.HIRED, Stage.REJECTED):
            make_application(job=self.job, stage=stage)
        make_application(job=other_job, stage=Stage.SCREENING)
        before, history = snapshot(self.job), StageChange.objects.count()
        close_job(self.job)
        self.assertEqual(snapshot(self.job), before)
        reopen_job(self.job)
        self.assertEqual(snapshot(self.job), before)
        self.assertEqual(StageChange.objects.count(), history)
        self.assertEqual(JobOpening.objects.get(pk=other_job.pk).status, JobStatus.OPEN)


class CloseReopenViewTests(TestCase):
    def setUp(self):
        self.job = make_job()
        self.client.force_login(make_recruiter())

    def test_close_redirects_to_the_job_with_a_message(self):
        response = self.client.post(close_url(self.job), follow=True)
        self.assertRedirects(response, detail_url(self.job))
        self.assertContains(response, "Data Analyst closed. It no longer accepts new applications.")
        self.assertContains(response, "alert-success")
        self.assertEqual(JobOpening.objects.get().status, JobStatus.CLOSED)

    def test_reopen_redirects_to_the_job_with_a_message(self):
        close_job(self.job)
        response = self.client.post(reopen_url(self.job), follow=True)
        self.assertRedirects(response, detail_url(self.job))
        self.assertContains(response, "Data Analyst reopened. It accepts new applications again.")
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_a_repeated_close_is_refused_with_a_clear_message(self):
        # A double-click, or a second tab still showing Close.
        self.client.post(close_url(self.job))
        response = self.client.post(close_url(self.job), follow=True)
        self.assertRedirects(response, detail_url(self.job))
        self.assertContains(response, "This job is already closed, so nothing was changed.")
        self.assertContains(response, "alert-error")
        self.assertEqual(JobOpening.objects.get().status, JobStatus.CLOSED)

    def test_a_stale_reopen_is_refused(self):
        response = self.client.post(reopen_url(self.job), follow=True)
        self.assertContains(response, "This job is already open, so nothing was changed.")
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_get_is_not_allowed(self):
        for url in (close_url(self.job), reopen_url(self.job)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_unknown_job_is_404(self):
        self.assertEqual(self.client.post("/jobs/999999/close/").status_code, 404)
        self.assertEqual(self.client.post("/jobs/999999/reopen/").status_code, 404)


class CloseReopenPermissionTests(TestCase):
    def test_recruiter_and_admin_can_close_and_reopen(self):
        # AC2
        for user in (make_recruiter(), make_admin()):
            with self.subTest(user=user.username):
                job = make_job(f"Role for {user.username}")
                self.client.force_login(user)
                self.client.post(close_url(job))
                self.assertEqual(JobOpening.objects.get(pk=job.pk).status, JobStatus.CLOSED)
                self.client.post(reopen_url(job))
                self.assertEqual(JobOpening.objects.get(pk=job.pk).status, JobStatus.OPEN)

    def test_view_only_user_gets_403_and_nothing_changes(self):
        job = make_job()
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.post(close_url(job)).status_code, 403)
        self.assertEqual(self.client.post(reopen_url(closed)).status_code, 403)
        self.assertEqual(JobOpening.objects.get(pk=job.pk).status, JobStatus.OPEN)
        self.assertEqual(JobOpening.objects.get(pk=closed.pk).status, JobStatus.CLOSED)

    def test_anonymous_post_is_redirected_to_login(self):
        job = make_job()
        response = self.client.post(close_url(job))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)


class JobDetailStatusTests(TestCase):
    def setUp(self):
        self.client.force_login(make_recruiter())

    def test_open_job_offers_close_only(self):
        job = make_job()
        response = self.client.get(detail_url(job))
        self.assertContains(response, f'<form method="post" action="{close_url(job)}"')
        self.assertContains(response, ">Close job</button>")
        self.assertNotContains(response, reopen_url(job))
        self.assertContains(response, ">Open<")

    def test_closed_job_offers_reopen_only_and_shows_job_closed(self):
        job = make_job(status=JobStatus.CLOSED)
        response = self.client.get(detail_url(job))
        self.assertContains(response, f'<form method="post" action="{reopen_url(job)}"')
        self.assertContains(response, ">Reopen job</button>")
        self.assertNotContains(response, close_url(job))
        self.assertContains(response, ">Job Closed<")

    def test_view_only_users_see_no_close_or_reopen(self):
        job = make_job()
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        self.client.force_login(make_viewer())
        self.assertNotContains(self.client.get(detail_url(job)), close_url(job))
        self.assertNotContains(self.client.get(detail_url(closed)), reopen_url(closed))

    def test_active_applications_note_on_a_closed_job(self):
        # US 23: unfinished work on a closed job is visible.
        job = make_job(status=JobStatus.OPEN)
        make_application(job=job, stage=Stage.INTERVIEW)
        make_application(job=job, stage=Stage.OFFER)
        make_application(job=job, stage=Stage.HIRED)
        JobOpening.objects.filter(pk=job.pk).update(status=JobStatus.CLOSED)
        response = self.client.get(detail_url(job))
        self.assertContains(response, "This job is closed but still has 2 active applications.")

    def test_singular_note(self):
        job = make_job()
        make_application(job=job, stage=Stage.SCREENING)
        JobOpening.objects.filter(pk=job.pk).update(status=JobStatus.CLOSED)
        self.assertContains(
            self.client.get(detail_url(job)),
            "This job is closed but still has 1 active application.",
        )

    def test_no_note_when_open_or_when_nothing_is_active(self):
        open_job = make_job()
        make_application(job=open_job, stage=Stage.INTERVIEW)
        finished = make_job("Finished Role")
        make_application(job=finished, stage=Stage.HIRED)
        make_application(job=finished, stage=Stage.WITHDRAWN)
        JobOpening.objects.filter(pk=finished.pk).update(status=JobStatus.CLOSED)
        for job in (open_job, finished):
            with self.subTest(job=job.title):
                self.assertNotContains(self.client.get(detail_url(job)), "still has")
