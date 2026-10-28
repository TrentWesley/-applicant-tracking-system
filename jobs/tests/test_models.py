from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from jobs.models import EmploymentType, JobOpening, JobSkill, JobStatus, Skill, WorkMode
from jobs.tests.utils import make_job, make_skill


class SkillNameConstraintTests(TestCase):
    def test_name_differing_only_in_case_is_refused_by_the_database(self):
        make_skill("Python")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_skill("PYTHON")
        self.assertEqual(Skill.objects.count(), 1)

    def test_identical_name_is_refused_by_the_database(self):
        make_skill("SQL")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_skill("SQL")

    def test_different_names_are_allowed(self):
        make_skill("Python")
        make_skill("Python 3")
        self.assertEqual(Skill.objects.count(), 2)

    def test_model_validation_reports_the_duplicate(self):
        make_skill("Python")
        with self.assertRaisesMessage(ValidationError, "A skill with this name already exists."):
            Skill(name="python").full_clean()

    def test_skills_are_listed_alphabetically_ignoring_case(self):
        for name in ("sql", "Excel", "python"):
            make_skill(name)
        self.assertEqual([s.name for s in Skill.objects.all()], ["Excel", "python", "sql"])

    def test_str_is_the_name(self):
        self.assertEqual(str(make_skill("Tableau")), "Tableau")


class JobOpeningFieldTests(TestCase):
    def test_employment_type_choices_are_the_fixed_list(self):
        self.assertEqual(
            EmploymentType.labels, ["Full-time", "Part-time", "Contract", "Internship"]
        )

    def test_work_mode_choices_are_the_fixed_list(self):
        self.assertEqual(WorkMode.labels, ["On-site", "Remote", "Hybrid"])

    def test_status_choices_are_open_and_closed(self):
        self.assertEqual(JobStatus.labels, ["Open", "Closed"])

    def test_a_new_job_is_open(self):
        self.assertEqual(make_job().status, JobStatus.OPEN)

    def test_status_is_not_editable_on_forms(self):
        # Status changes only through the Close and Reopen actions (Phase 7), never a form.
        self.assertFalse(JobOpening._meta.get_field("status").editable)

    def test_title_employment_type_and_work_mode_are_required(self):
        with self.assertRaises(ValidationError) as caught:
            JobOpening().full_clean()
        self.assertEqual(
            set(caught.exception.message_dict), {"title", "employment_type", "work_mode"}
        )

    def test_department_location_description_and_skills_are_optional(self):
        job = JobOpening(
            title="Analyst", employment_type=EmploymentType.CONTRACT, work_mode=WorkMode.REMOTE
        )
        job.full_clean()

    def test_invalid_choice_values_are_refused(self):
        job = JobOpening(title="Analyst", employment_type="seasonal", work_mode="moon")
        with self.assertRaises(ValidationError) as caught:
            job.full_clean()
        self.assertEqual(set(caught.exception.message_dict), {"employment_type", "work_mode"})

    def test_timestamps_are_set(self):
        job = make_job()
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)

    def test_str_and_absolute_url(self):
        job = make_job("Data Analyst")
        self.assertEqual(str(job), "Data Analyst")
        self.assertEqual(job.get_absolute_url(), f"/jobs/{job.pk}/")


class JobSkillRelationshipTests(TestCase):
    def test_a_job_can_have_many_skills_and_a_skill_many_jobs(self):
        python, sql = make_skill("Python"), make_skill("SQL")
        analyst = make_job("Analyst", skills=[python, sql])
        engineer = make_job("Engineer", skills=[python])
        self.assertEqual(set(analyst.skills.all()), {python, sql})
        self.assertEqual(set(python.jobs.all()), {analyst, engineer})

    def test_a_skill_is_assigned_to_a_job_only_once(self):
        python = make_skill("Python")
        job = make_job(skills=[python])
        with self.assertRaises(IntegrityError), transaction.atomic():
            JobSkill.objects.create(job=job, skill=python)

    def test_deleting_a_used_skill_is_protected_and_keeps_the_assignment(self):
        python = make_skill("Python")
        job = make_job(skills=[python])
        with self.assertRaises(ProtectedError):
            python.delete()
        self.assertEqual(list(job.skills.all()), [python])

    def test_deleting_a_job_removes_its_skill_assignments_but_not_the_skills(self):
        python = make_skill("Python")
        make_job(skills=[python]).delete()
        self.assertFalse(JobSkill.objects.exists())
        self.assertTrue(Skill.objects.filter(pk=python.pk).exists())

    def test_assignment_str_names_the_job_and_skill(self):
        job = make_job("Analyst", skills=[make_skill("SQL")])
        self.assertEqual(str(JobSkill.objects.get(job=job)), "Analyst needs SQL")
