"""Phase 13: "Hired for…" on the candidate detail page (US 19; AC18)."""

from django.test import TestCase

from candidates.services import archive_candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import database_state, make_recruiter, queries_for
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import Stage
from pipeline.tests.utils import make_application


def hired_badge(job):
    return f'href="{job.get_absolute_url()}" class="badge badge-success">Hired for {job}</a>'


class HiredForTests(TestCase):
    def setUp(self):
        self.client.force_login(make_recruiter())
        self.candidate = make_candidate()
        self.backend = make_job("Backend Developer")
        self.analyst = make_job("Data Analyst")

    def get(self):
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return response

    def test_one_badge_per_hired_job_linking_to_the_job(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        make_application(candidate=self.candidate, job=self.analyst, stage=Stage.HIRED)
        response = self.get()
        self.assertContains(response, hired_badge(self.backend), count=1)
        self.assertContains(response, hired_badge(self.analyst), count=1)

    def test_other_stages_are_not_hired(self):
        for stage, title in ((Stage.OFFER, "Offer job"), (Stage.REJECTED, "Rejected job")):
            make_application(candidate=self.candidate, job=make_job(title), stage=stage)
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        response = self.get()
        self.assertContains(response, ">Hired for ", count=1)  # one badge
        self.assertContains(response, hired_badge(self.backend))

    def test_never_hired_shows_nothing(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.WITHDRAWN)
        self.assertNotContains(self.get(), "Hired for")

    def test_shows_for_an_archived_candidate(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        archive_candidate(self.candidate)
        response = self.get()
        self.assertContains(response, ">Archived</span>")
        self.assertContains(response, hired_badge(self.backend))

    def test_shows_for_a_closed_job(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        JobOpening.objects.filter(pk=self.backend.pk).update(status=JobStatus.CLOSED)
        self.assertContains(self.get(), hired_badge(self.backend))

    def test_the_applications_table_marks_closed_jobs_and_offers(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.OFFER)
        make_application(candidate=self.candidate, job=self.analyst, stage=Stage.SCREENING)
        JobOpening.objects.filter(pk=self.backend.pk).update(status=JobStatus.CLOSED)
        response = self.get()
        self.assertContains(response, "Job Closed", count=1)
        self.assertContains(response, "Awaiting Decision", count=1)

    def test_viewing_changes_nothing(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        before = database_state()
        self.get()
        self.assertEqual(database_state(), before)

    def test_query_count_does_not_grow_with_applications(self):
        make_application(candidate=self.candidate, job=self.backend, stage=Stage.HIRED)
        one = queries_for(self.client, self.candidate.get_absolute_url())
        for number in range(3):
            job = make_job(f"Job {number}")
            make_application(candidate=self.candidate, job=job, stage=Stage.HIRED)
        self.assertEqual(queries_for(self.client, self.candidate.get_absolute_url()), one)
