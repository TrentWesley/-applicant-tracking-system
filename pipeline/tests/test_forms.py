from django.test import TestCase
from django.utils import timezone

from candidates.tests.utils import make_candidate
from jobs.models import JobStatus
from jobs.tests.utils import make_job
from pipeline.forms import (
    ARCHIVED_CANDIDATE_CHOICE_MESSAGE,
    CLOSED_JOB_CHOICE_MESSAGE,
    ApplicationForm,
)
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE
from pipeline.tests.utils import make_application


class ApplicationFormTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate(first_name="Ann", last_name="Lee", email="ann@example.com")
        self.job = make_job("Data Analyst", department="Finance")

    def data(self, **extra):
        return {"candidate": self.candidate.pk, "job_opening": self.job.pk, "notes": ""} | extra

    def test_valid_pair_is_accepted_and_notes_are_optional(self):
        form = ApplicationForm(data=self.data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_candidate_and_job_are_required(self):
        form = ApplicationForm(data={})
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {"candidate", "job_opening"})

    def test_form_has_no_stage_or_creator_fields(self):
        self.assertEqual(list(ApplicationForm().fields), ["candidate", "job_opening", "notes"])

    def test_only_open_jobs_are_offered(self):
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        jobs = list(ApplicationForm().fields["job_opening"].queryset)
        self.assertIn(self.job, jobs)
        self.assertNotIn(closed, jobs)

    def test_only_active_candidates_are_offered(self):
        archived = make_candidate(email="gone@example.com", archived_at=timezone.now())
        candidates = list(ApplicationForm().fields["candidate"].queryset)
        self.assertIn(self.candidate, candidates)
        self.assertNotIn(archived, candidates)

    def test_choices_identify_the_candidate_and_job(self):
        form = ApplicationForm()
        self.assertIn(("Ann Lee (ann@example.com)"), str(form["candidate"]))
        self.assertIn("Data Analyst (Finance)", str(form["job_opening"]))

    def test_posting_a_closed_job_is_refused_with_a_clear_reason(self):
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        form = ApplicationForm(data=self.data(job_opening=closed.pk))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["job_opening"], [CLOSED_JOB_CHOICE_MESSAGE])

    def test_posting_an_archived_candidate_is_refused_with_a_clear_reason(self):
        archived = make_candidate(email="gone@example.com", archived_at=timezone.now())
        form = ApplicationForm(data=self.data(candidate=archived.pk))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["candidate"], [ARCHIVED_CANDIDATE_CHOICE_MESSAGE])

    def test_duplicate_pair_is_refused_with_the_duplicate_message(self):
        make_application(self.candidate, self.job)
        form = ApplicationForm(data=self.data())
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors(), [DUPLICATE_APPLICATION_MESSAGE])
