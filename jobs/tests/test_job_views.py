from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.models import EmploymentType, JobOpening, JobStatus, WorkMode
from jobs.tests.utils import make_job, make_skill

LIST_URL = reverse("jobs:job_list")
CREATE_URL = reverse("jobs:job_create")

VALID = {
    "title": "Data Analyst",
    "department": "Finance",
    "location": "Amarillo, TX",
    "employment_type": EmploymentType.FULL_TIME,
    "work_mode": WorkMode.HYBRID,
    "description": "Build weekly reports.",
}


def detail_url(job):
    return reverse("jobs:job_detail", args=[job.pk])


def edit_url(job):
    return reverse("jobs:job_update", args=[job.pk])


def make_viewer():
    """A staff user who may only view job openings."""
    user = make_user("viewer")
    user.user_permissions.add(Permission.objects.get(codename="view_jobopening"))
    return user


class StaffTestCase(TestCase):
    def setUp(self):
        self.staff = [make_recruiter(), make_admin()]


class JobListTests(StaffTestCase):
    def test_recruiter_and_admin_see_jobs_with_status_and_skills(self):
        python = make_skill("Python")
        job = make_job("Data Analyst", skills=[python], department="Finance")
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(LIST_URL)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "jobs/job_list.html")
                self.assertContains(response, "<h1", count=1)
                self.assertContains(response, "Job Openings</h1>")
                self.assertContains(response, f'href="{detail_url(job)}"')
                self.assertContains(response, "Finance")
                self.assertContains(response, "Full-time")
                self.assertContains(response, "Hybrid")
                self.assertContains(response, "Python")
                self.assertContains(response, ">Open<")

    def test_closed_jobs_are_listed_with_a_closed_badge(self):
        make_job("Old Role", status=JobStatus.CLOSED)
        self.client.force_login(self.staff[0])
        response = self.client.get(LIST_URL)
        self.assertContains(response, "Old Role")
        self.assertContains(response, ">Closed<")

    def test_empty_list_says_so(self):
        self.client.force_login(self.staff[0])
        self.assertContains(self.client.get(LIST_URL), "No job openings yet.")

    def test_add_button_shown_to_users_who_can_add(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(LIST_URL), f'href="{CREATE_URL}"')

    def test_add_button_hidden_from_view_only_users(self):
        self.client.force_login(make_viewer())
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{CREATE_URL}"')


class JobSkillFilterTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.python, self.sql = make_skill("Python"), make_skill("SQL")
        self.excel = make_skill("Excel")
        self.analyst = make_job("Analyst", skills=[self.python, self.sql])
        self.engineer = make_job("Engineer", skills=[self.python], status=JobStatus.CLOSED)
        self.clerk = make_job("Clerk", skills=[self.excel])
        self.intern = make_job("Intern")
        self.client.force_login(self.staff[0])

    def jobs_for(self, query):
        response = self.client.get(LIST_URL, query)
        self.assertEqual(response.status_code, 200)
        return list(response.context["jobs"])

    def test_filter_returns_exactly_the_jobs_with_that_skill(self):
        self.assertEqual(self.jobs_for({"skill": self.python.pk}), [self.analyst, self.engineer])
        self.assertEqual(self.jobs_for({"skill": self.sql.pk}), [self.analyst])
        self.assertEqual(self.jobs_for({"skill": self.excel.pk}), [self.clerk])

    def test_no_filter_returns_every_job(self):
        self.assertEqual(self.jobs_for({}), [self.analyst, self.clerk, self.engineer, self.intern])

    def test_unused_skill_returns_no_jobs_with_a_message(self):
        unused = make_skill("Go")
        self.assertEqual(self.jobs_for({"skill": unused.pk}), [])
        response = self.client.get(LIST_URL, {"skill": unused.pk})
        self.assertContains(response, "No job openings need Go.")

    def test_invalid_skill_value_is_ignored(self):
        for value in ("abc", "999999"):
            with self.subTest(value=value):
                self.assertEqual(len(self.jobs_for({"skill": value})), 4)

    def test_filter_form_offers_every_skill_and_keeps_the_selection(self):
        response = self.client.get(LIST_URL, {"skill": self.sql.pk})
        self.assertContains(response, '<form method="get"')
        self.assertContains(response, f'<option value="{self.sql.pk}" selected>SQL</option>')
        self.assertContains(response, f'<option value="{self.excel.pk}">Excel</option>')
        self.assertContains(response, f'href="{LIST_URL}"')  # clear-filter link

    def test_skill_badges_link_to_the_filtered_list(self):
        response = self.client.get(LIST_URL)
        self.assertContains(response, f'href="{LIST_URL}?skill={self.sql.pk}"')


class JobDetailTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.job = make_job(
            "Data Analyst",
            skills=[make_skill("Python"), make_skill("SQL")],
            department="Finance",
            location="Amarillo, TX",
            employment_type=EmploymentType.CONTRACT,
            work_mode=WorkMode.REMOTE,
            description="Build weekly reports.",
        )

    def test_detail_shows_every_field_and_the_skills(self):
        expected = [
            "Finance",
            "Amarillo, TX",
            "Contract",
            "Remote",
            ">Open<",
            "Python",
            "SQL",
            "Build weekly reports.",
        ]
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url(self.job))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Data Analyst</h1>")
                for text in expected:
                    self.assertContains(response, text)

    def test_edit_button_shown_to_users_who_can_change(self):
        self.client.force_login(self.staff[0])
        self.assertContains(self.client.get(detail_url(self.job)), f'href="{edit_url(self.job)}"')

    def test_edit_button_hidden_from_view_only_users(self):
        self.client.force_login(make_viewer())
        response = self.client.get(detail_url(self.job))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{edit_url(self.job)}"')

    def test_job_without_skills_says_so(self):
        job = make_job("Intern")
        self.client.force_login(self.staff[0])
        self.assertContains(self.client.get(detail_url(job)), "No skills listed.")

    def test_unknown_job_is_404(self):
        self.client.force_login(self.staff[0])
        self.assertEqual(self.client.get("/jobs/999999/").status_code, 404)


class JobCreateTests(StaffTestCase):
    def test_form_page_renders_labelled_fields_and_no_status(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add job opening</h1>")
        for field in ("title", "department", "location", "employment_type", "work_mode"):
            self.assertContains(response, f'<label for="id_{field}"')
        self.assertNotContains(response, 'name="status"')

    def test_skill_checkboxes_are_grouped_in_a_fieldset_with_a_legend(self):
        make_skill("Python")
        self.client.force_login(self.staff[0])
        response = self.client.get(CREATE_URL)
        self.assertContains(response, "<fieldset")
        self.assertContains(response, "Skills</legend>")
        self.assertContains(response, 'type="checkbox" name="skills"')

    def test_recruiter_and_admin_create_an_open_job_and_land_on_detail(self):
        python, sql = make_skill("Python"), make_skill("SQL")
        for index, user in enumerate(self.staff):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                title = f"Analyst {index}"
                data = VALID | {"title": title, "skills": [python.pk, sql.pk]}
                response = self.client.post(CREATE_URL, data, follow=True)
                job = JobOpening.objects.get(title=title)
                self.assertRedirects(response, detail_url(job))
                self.assertContains(response, f"Job opening {title} added.")
                self.assertEqual(job.status, JobStatus.OPEN)
                self.assertEqual(set(job.skills.all()), {python, sql})

    def test_posted_status_is_ignored(self):
        self.client.force_login(self.staff[0])
        self.client.post(CREATE_URL, VALID | {"status": JobStatus.CLOSED})
        self.assertEqual(JobOpening.objects.get().status, JobStatus.OPEN)

    def test_missing_required_field_or_invalid_choice_is_refused(self):
        self.client.force_login(self.staff[0])
        for change in ({"title": ""}, {"work_mode": ""}, {"employment_type": "seasonal"}):
            with self.subTest(change=change):
                response = self.client.post(CREATE_URL, VALID | change)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(JobOpening.objects.exists())


class JobUpdateTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.python, self.sql = make_skill("Python"), make_skill("SQL")
        self.job = make_job("Data Analyst", skills=[self.python])

    def test_form_is_prefilled(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(edit_url(self.job))
        self.assertContains(response, "Edit Data Analyst</h1>")
        self.assertContains(response, 'value="Data Analyst"')
        self.assertEqual(list(response.context["form"]["skills"].value()), [self.python.pk])
        self.assertContains(response, "checked", count=1)

    def test_recruiter_and_admin_edit_fields_and_skills(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                title = f"Analyst ({user.username})"
                data = VALID | {"title": title, "skills": [self.sql.pk]}
                response = self.client.post(edit_url(self.job), data, follow=True)
                self.assertRedirects(response, detail_url(self.job))
                self.assertContains(response, "changes saved")
                self.job.refresh_from_db()
                self.assertEqual(self.job.title, title)
                self.assertEqual(list(self.job.skills.all()), [self.sql])

    def test_all_skills_can_be_removed(self):
        self.client.force_login(self.staff[0])
        self.client.post(edit_url(self.job), VALID)
        self.assertFalse(self.job.skills.exists())

    def test_posted_status_is_ignored_on_open_and_closed_jobs(self):
        closed = make_job("Old Role", status=JobStatus.CLOSED)
        self.client.force_login(self.staff[0])
        self.client.post(edit_url(self.job), VALID | {"status": JobStatus.CLOSED})
        self.client.post(edit_url(closed), VALID | {"status": JobStatus.OPEN})
        self.job.refresh_from_db()
        closed.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.OPEN)
        self.assertEqual(closed.status, JobStatus.CLOSED)

    def test_edit_applies_the_same_validation_as_create(self):
        self.client.force_login(self.staff[0])
        for change in ({"title": ""}, {"work_mode": "moon"}):
            with self.subTest(change=change):
                response = self.client.post(edit_url(self.job), VALID | change)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.job.refresh_from_db()
                self.assertEqual(self.job.title, "Data Analyst")


class JobPermissionTests(TestCase):
    def setUp(self):
        self.job = make_job()

    def urls(self):
        return [LIST_URL, CREATE_URL, detail_url(self.job), edit_url(self.job)]

    def test_user_without_permissions_gets_403_everywhere(self):
        self.client.force_login(make_user("nobody"))
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_forbidden_create_writes_nothing(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.post(CREATE_URL, VALID).status_code, 403)
        self.assertEqual(JobOpening.objects.count(), 1)

    def test_forbidden_edit_changes_nothing(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.post(edit_url(self.job), VALID).status_code, 403)
        self.job.refresh_from_db()
        self.assertEqual(self.job.department, "")

    def test_view_only_user_can_view_but_not_add_or_edit(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.get(LIST_URL).status_code, 200)
        self.assertEqual(self.client.get(detail_url(self.job)).status_code, 200)
        self.assertEqual(self.client.get(CREATE_URL).status_code, 403)
        self.assertEqual(self.client.get(edit_url(self.job)).status_code, 403)

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"/accounts/login/?next={url}",
                    fetch_redirect_response=False,
                )


class JobNavigationTests(StaffTestCase):
    def test_job_openings_link_is_current_on_every_job_page_and_skills_is_not(self):
        job = make_job()
        self.client.force_login(self.staff[1])
        marked = f'href="{LIST_URL}" class="menu-active" aria-current="page"'
        skills_marked = f'href="{reverse("jobs:skill_list")}" class="menu-active"'
        for url in (LIST_URL, CREATE_URL, detail_url(job), edit_url(job)):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, marked)
                self.assertNotContains(response, skills_marked)
