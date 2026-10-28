from django import forms
from django.test import TestCase

from jobs.forms import JobOpeningForm, SkillForm
from jobs.models import DUPLICATE_SKILL_MESSAGE, EmploymentType, JobStatus, WorkMode
from jobs.tests.utils import make_job, make_skill

VALID_JOB = {
    "title": "Data Analyst",
    "department": "Finance",
    "location": "Amarillo, TX",
    "description": "Build reports.",
    "employment_type": EmploymentType.FULL_TIME,
    "work_mode": WorkMode.HYBRID,
}


class SkillFormTests(TestCase):
    def test_new_unique_name_is_accepted(self):
        self.assertTrue(SkillForm(data={"name": "Python"}).is_valid())

    def test_name_is_required(self):
        form = SkillForm(data={"name": "  "})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_duplicate_in_another_case_is_refused_on_the_name_field(self):
        make_skill("Python")
        form = SkillForm(data={"name": "pYTHON"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"], [DUPLICATE_SKILL_MESSAGE])

    def test_surrounding_spaces_do_not_dodge_the_duplicate_check(self):
        make_skill("SQL")
        form = SkillForm(data={"name": "  sql "})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"], [DUPLICATE_SKILL_MESSAGE])

    def test_renaming_a_skill_to_its_own_name_in_another_case_is_allowed(self):
        skill = make_skill("python")
        form = SkillForm(data={"name": "Python"}, instance=skill)
        self.assertTrue(form.is_valid(), form.errors)

    def test_renaming_to_another_skills_name_is_refused(self):
        make_skill("SQL")
        skill = make_skill("Python")
        form = SkillForm(data={"name": "Sql"}, instance=skill)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"], [DUPLICATE_SKILL_MESSAGE])


class JobOpeningFormTests(TestCase):
    def test_valid_job_is_accepted_and_starts_open(self):
        form = JobOpeningForm(data=VALID_JOB)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().status, JobStatus.OPEN)

    def test_form_has_no_status_field(self):
        self.assertNotIn("status", JobOpeningForm().fields)

    def test_title_employment_type_and_work_mode_are_required(self):
        for field in ("title", "employment_type", "work_mode"):
            with self.subTest(field=field):
                form = JobOpeningForm(data=VALID_JOB | {field: ""})
                self.assertFalse(form.is_valid())
                self.assertEqual(list(form.errors), [field])

    def test_department_location_description_and_skills_may_be_blank(self):
        data = VALID_JOB | {"department": "", "location": "", "description": ""}
        self.assertTrue(JobOpeningForm(data=data).is_valid())

    def test_invalid_choice_values_are_refused(self):
        for field in ("employment_type", "work_mode"):
            with self.subTest(field=field):
                form = JobOpeningForm(data=VALID_JOB | {field: "seasonal"})
                self.assertFalse(form.is_valid())
                self.assertEqual(list(form.errors), [field])

    def test_unknown_skill_is_refused(self):
        form = JobOpeningForm(data=VALID_JOB | {"skills": ["999999"]})
        self.assertFalse(form.is_valid())
        self.assertIn("skills", form.errors)

    def test_several_skills_can_be_assigned(self):
        python, sql = make_skill("Python"), make_skill("SQL")
        form = JobOpeningForm(data=VALID_JOB | {"skills": [python.pk, sql.pk]})
        job = form.save()
        self.assertEqual(set(job.skills.all()), {python, sql})

    def test_skills_are_chosen_with_checkboxes(self):
        self.assertIsInstance(
            JobOpeningForm().fields["skills"].widget, forms.CheckboxSelectMultiple
        )

    def test_posted_status_is_ignored_on_create(self):
        job = JobOpeningForm(data=VALID_JOB | {"status": JobStatus.CLOSED}).save()
        self.assertEqual(job.status, JobStatus.OPEN)

    def test_posted_status_is_ignored_on_edit(self):
        job = make_job(status=JobStatus.CLOSED)
        form = JobOpeningForm(data=VALID_JOB | {"status": JobStatus.OPEN}, instance=job)
        form.save()
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CLOSED)

    def test_skill_checkboxes_get_the_daisyui_checkbox_class(self):
        self.assertEqual(JobOpeningForm().fields["skills"].widget.attrs["class"], "checkbox")

    def test_checkbox_class_is_on_each_input_not_the_wrapping_div(self):
        make_skill("Python")
        html = str(JobOpeningForm()["skills"])
        self.assertIn('<div id="id_skills">', html)
        self.assertIn('class="checkbox" id="id_skills_0"', html)
