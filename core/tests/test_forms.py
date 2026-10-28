"""SaveOnlyFormFieldsMixin: each edit form's UPDATE sets only that form's columns."""

import re

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from candidates.forms import CandidateForm
from candidates.models import Candidate
from candidates.tests.utils import make_candidate
from jobs.forms import JobOpeningForm
from jobs.models import EmploymentType, JobOpening, WorkMode
from jobs.tests.utils import make_job, make_skill
from pipeline.forms import ApplicationNotesForm
from pipeline.tests.utils import make_application


def updated_columns(queries, table):
    """The columns set by the UPDATE statements on `table`."""
    columns = set()
    for query in queries:
        sql = query["sql"]
        if sql.startswith(f'UPDATE "{table}" SET'):
            assignments = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
            columns |= set(re.findall(r'"(\w+)" = ', assignments))
    return columns


class SaveOnlyFormFieldsMixinTests(TestCase):
    def save_and_capture(self, form):
        self.assertTrue(form.is_valid(), form.errors)
        with CaptureQueriesContext(connection) as captured:
            instance = form.save()
        return instance, captured.captured_queries

    def test_candidate_edit_sets_its_fields_and_updated_at_never_archived_at(self):
        candidate = make_candidate()
        before = candidate.updated_at
        data = {
            "first_name": "Ann",
            "last_name": "Lee",
            "email": "ann.lee@example.com",
            "source": "referral",
            "phone": "806-555-0100",
        }
        saved, queries = self.save_and_capture(CandidateForm(data, instance=candidate))
        self.assertEqual(
            updated_columns(queries, "candidates_candidate"),
            {*CandidateForm.Meta.fields, "updated_at"},
        )
        self.assertGreater(Candidate.objects.get().updated_at, before)
        self.assertEqual(saved.phone, "806-555-0100")

    def test_job_edit_sets_its_columns_and_updated_at_never_status_and_saves_skills(self):
        job = make_job()
        python = make_skill("Python")
        data = {
            "title": "Senior Data Analyst",
            "employment_type": EmploymentType.FULL_TIME,
            "work_mode": WorkMode.REMOTE,
            "skills": [python.pk],
        }
        _saved, queries = self.save_and_capture(JobOpeningForm(data, instance=job))
        columns = set(JobOpeningForm.Meta.fields) - {"skills"}  # many-to-many, not a column
        self.assertEqual(updated_columns(queries, "jobs_jobopening"), {*columns, "updated_at"})
        self.assertEqual(list(JobOpening.objects.get().skills.all()), [python])

    def test_application_notes_edit_sets_only_notes(self):
        # Application has no updated_at, so only notes is written.
        application = make_application()
        _saved, queries = self.save_and_capture(
            ApplicationNotesForm({"notes": "Strong SQL."}, instance=application)
        )
        self.assertEqual(updated_columns(queries, "pipeline_application"), {"notes"})

    def test_new_rows_still_save_every_field(self):
        data = {
            "first_name": "Bo",
            "last_name": "Diaz",
            "email": "bo@example.com",
            "source": "referral",
        }
        candidate, queries = self.save_and_capture(CandidateForm(data))
        self.assertTrue(
            any(q["sql"].startswith('INSERT INTO "candidates_candidate"') for q in queries)
        )
        self.assertIsNone(Candidate.objects.get(pk=candidate.pk).archived_at)
