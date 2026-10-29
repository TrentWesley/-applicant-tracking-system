"""Phase 13: the job detail summary: applications, active count, hired count (US 25; AC18)."""

from django.test import TestCase

from candidates.services import archive_candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import database_state, make_recruiter, queries_for
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import Stage
from pipeline.tests.utils import make_application


def close(job):
    JobOpening.objects.filter(pk=job.pk).update(status=JobStatus.CLOSED)


class JobSummaryTests(TestCase):
    def setUp(self):
        self.client.force_login(make_recruiter())
        self.job = make_job("Backend Developer")

    def get(self):
        response = self.client.get(self.job.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return response

    def add(self, stage, first_name="Ann", **candidate):
        number = self.job.applications.count() + 1
        candidate = make_candidate(
            email=f"{first_name.lower()}{number}@example.com", first_name=first_name, **candidate
        )
        return make_application(candidate=candidate, job=self.job, stage=stage)

    def test_counts_cover_every_stage_group(self):
        for stage in (Stage.APPLIED, Stage.OFFER, Stage.HIRED, Stage.HIRED, Stage.REJECTED):
            self.add(stage)
        self.add(Stage.WITHDRAWN)
        response = self.get()
        self.assertEqual(response.context["counts"], {"total": 6, "active": 2, "hired": 2})
        self.assertContains(response, 'id="job-active-count">2<')
        self.assertContains(response, 'id="job-hired-count">2<')

    def test_the_hired_count_includes_archived_candidates(self):
        hired = self.add(Stage.HIRED)
        archive_candidate(hired.candidate)
        self.add(Stage.HIRED)
        self.assertContains(self.get(), 'id="job-hired-count">2<')

    def test_counts_on_a_closed_job(self):
        self.add(Stage.INTERVIEW)
        self.add(Stage.HIRED)
        close(self.job)
        response = self.get()
        self.assertEqual(response.context["counts"], {"total": 2, "active": 1, "hired": 1})
        self.assertContains(response, "still has 1 active application.")  # the Phase 7 note

    def test_lists_every_application_with_its_stage_and_link(self):
        applied = self.add(Stage.APPLIED, first_name="Ava")
        rejected = self.add(Stage.REJECTED, first_name="Wyatt")
        response = self.get()
        for application in (applied, rejected):
            self.assertContains(response, f'href="{application.get_absolute_url()}"')
        self.assertContains(response, ">Applied</span>")
        self.assertContains(response, ">Rejected</span>")

    def test_archived_candidates_are_listed_with_a_badge(self):
        hired = self.add(Stage.HIRED, first_name="Leo")
        archive_candidate(hired.candidate)
        self.add(Stage.APPLIED, first_name="Ava")
        response = self.get()
        self.assertContains(response, f'href="{hired.get_absolute_url()}"')
        self.assertContains(response, "Archived", count=1)

    def test_offers_show_awaiting_decision(self):
        self.add(Stage.OFFER)
        self.add(Stage.FINAL_REVIEW)
        self.assertContains(self.get(), "Awaiting Decision", count=1)

    def test_empty_state(self):
        response = self.get()
        self.assertEqual(response.context["counts"], {"total": 0, "active": 0, "hired": 0})
        self.assertContains(response, "No applications yet.")
        self.assertContains(response, 'id="job-hired-count">0<')

    def test_viewing_changes_nothing(self):
        self.add(Stage.OFFER)
        self.add(Stage.HIRED)
        before = database_state()
        self.get()
        self.assertEqual(database_state(), before)

    def test_query_count_does_not_grow_with_applications(self):
        self.add(Stage.APPLIED)
        one = queries_for(self.client, self.job.get_absolute_url())
        for stage in (Stage.OFFER, Stage.HIRED, Stage.REJECTED):
            self.add(stage)
        self.assertEqual(queries_for(self.client, self.job.get_absolute_url()), one)
