from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.models import DUPLICATE_SKILL_MESSAGE, JobStatus, Skill
from jobs.tests.utils import make_job, make_skill

LIST_URL = reverse("jobs:skill_list")
CREATE_URL = reverse("jobs:skill_create")


def edit_url(skill):
    return reverse("jobs:skill_update", args=[skill.pk])


def delete_url(skill):
    return reverse("jobs:skill_delete", args=[skill.pk])


class SkillListTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())

    def test_admin_sees_skills_with_rename_and_delete_links(self):
        skill = make_skill("Python")
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/skill_list.html")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Skills</h1>")
        self.assertContains(response, "Python")
        self.assertContains(response, f'href="{edit_url(skill)}"')
        self.assertContains(response, f'href="{delete_url(skill)}"')
        self.assertContains(response, f'href="{CREATE_URL}"')

    def test_list_shows_how_many_jobs_use_each_skill(self):
        python = make_skill("Python")
        make_job("Analyst", skills=[python])
        make_job("Engineer", skills=[python], status=JobStatus.CLOSED)
        response = self.client.get(LIST_URL)
        self.assertEqual(response.context["skills"].get(pk=python.pk).job_count, 2)

    def test_skills_are_listed_alphabetically_ignoring_case(self):
        # Meta.ordering doesn't apply to the GROUP BY query that counts jobs, so the view orders.
        go, excel, python = make_skill("go"), make_skill("Excel"), make_skill("Python")
        make_job(skills=[python, go])
        response = self.client.get(LIST_URL)
        self.assertEqual(list(response.context["skills"]), [excel, go, python])

    def test_empty_list_says_so(self):
        self.assertContains(self.client.get(LIST_URL), "No skills yet.")


class SkillCreateTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())

    def test_form_page_renders(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, "Add skill</h1>")
        self.assertContains(response, '<label for="id_name"')

    def test_admin_creates_a_skill_and_returns_to_the_list(self):
        response = self.client.post(CREATE_URL, {"name": "Tableau"}, follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Skill Tableau added.")
        self.assertTrue(Skill.objects.filter(name="Tableau").exists())

    def test_duplicate_in_another_case_is_refused_with_message(self):
        make_skill("Python")
        response = self.client.post(CREATE_URL, {"name": "PYTHON"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_SKILL_MESSAGE)
        self.assertEqual(Skill.objects.count(), 1)


class SkillRenameTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())
        self.skill = make_skill("Pyhton")

    def test_admin_renames_a_skill(self):
        response = self.client.get(edit_url(self.skill))
        self.assertContains(response, "Rename Pyhton</h1>")
        self.assertContains(response, 'value="Pyhton"')
        response = self.client.post(edit_url(self.skill), {"name": "Python"}, follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Skill renamed to Python.")
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python")

    def test_rename_keeps_the_skill_on_its_jobs(self):
        job = make_job(skills=[self.skill])
        self.client.post(edit_url(self.skill), {"name": "Python"})
        self.assertEqual(list(job.skills.values_list("name", flat=True)), ["Python"])

    def test_rename_to_an_existing_name_is_refused(self):
        make_skill("SQL")
        response = self.client.post(edit_url(self.skill), {"name": "sql"})
        self.assertContains(response, DUPLICATE_SKILL_MESSAGE)
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Pyhton")


class SkillDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())
        self.skill = make_skill("Python")

    def test_confirmation_page_asks_before_deleting(self):
        response = self.client.get(delete_url(self.skill))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Python?</h1>")
        self.assertContains(response, f'<form method="post" action="{delete_url(self.skill)}"')
        self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())

    def test_admin_deletes_an_unused_skill(self):
        response = self.client.post(delete_url(self.skill), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Skill Python deleted.")
        self.assertFalse(Skill.objects.filter(pk=self.skill.pk).exists())

    def test_deleting_a_skill_used_by_an_open_or_closed_job_is_refused_and_lists_them(self):
        cases = {JobStatus.OPEN: "Data Analyst", JobStatus.CLOSED: "Report Writer"}
        for status, title in cases.items():
            with self.subTest(status=status):
                job = make_job(title, skills=[self.skill], status=status)
                response = self.client.post(delete_url(self.skill))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "can't be deleted")
                self.assertContains(response, f'href="{job.get_absolute_url()}"')
                self.assertContains(response, title)
                self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())
                self.assertEqual(list(job.skills.all()), [self.skill])
                job.skills.clear()

    def test_confirmation_page_for_a_used_skill_lists_the_jobs_and_offers_no_delete(self):
        job = make_job("Data Analyst", skills=[self.skill])
        response = self.client.get(delete_url(self.skill))
        self.assertContains(response, f'href="{job.get_absolute_url()}"')
        self.assertNotContains(response, f'<form method="post" action="{delete_url(self.skill)}"')


class SkillPermissionTests(TestCase):
    def setUp(self):
        self.skill = make_skill("Python")

    def urls(self):
        return [LIST_URL, CREATE_URL, edit_url(self.skill), delete_url(self.skill)]

    def test_recruiter_gets_403_on_every_skill_page(self):
        self.client.force_login(make_recruiter())
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_recruiter_cannot_create_rename_or_delete_skills(self):
        self.client.force_login(make_recruiter())
        self.assertEqual(self.client.post(CREATE_URL, {"name": "SQL"}).status_code, 403)
        self.assertEqual(self.client.post(edit_url(self.skill), {"name": "X"}).status_code, 403)
        self.assertEqual(self.client.post(delete_url(self.skill)).status_code, 403)
        self.assertEqual(list(Skill.objects.values_list("name", flat=True)), ["Python"])

    def test_superuser_can_manage_skills(self):
        self.client.force_login(User.objects.create_superuser("root", password="x"))
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_user_without_a_role_gets_403(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(self.client.get(LIST_URL).status_code, 403)

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"/accounts/login/?next={url}",
                    fetch_redirect_response=False,
                )


class SkillNavigationTests(TestCase):
    def test_skills_link_is_current_on_every_skill_page_and_job_openings_is_not(self):
        skill = make_skill()
        self.client.force_login(make_admin())
        skills_marked = f'href="{LIST_URL}" class="menu-active" aria-current="page"'
        jobs_marked = f'href="{reverse("jobs:job_list")}" class="menu-active"'
        for url in (LIST_URL, CREATE_URL, edit_url(skill), delete_url(skill)):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, skills_marked)
                self.assertNotContains(response, jobs_marked)
