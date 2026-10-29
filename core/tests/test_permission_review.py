"""
Phase 13: the permission review (AC1, AC2, AC3). Every row of the PRD permission table, for
anonymous users, Recruiters and Admins. Each request runs inside a transaction that is rolled
back, so every case starts from the same data.

- Allowed requests succeed (200, or a redirect after a POST that changed the data).
- Forbidden requests get 403 and change nothing.
- Anonymous requests are redirected to login and change nothing.
"""

from dataclasses import dataclass, field

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from candidates.services import archive_candidate
from candidates.tests.utils import make_candidate
from core.roles import ADMIN, RECRUITER
from core.tests.utils import database_state, make_admin, make_recruiter
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job, make_skill
from pipeline.tests.utils import make_application

NEW_PASSWORD = "plum-orchard-lantern-42"


@dataclass
class Case:
    """One request. `admin_only` rows are refused to Recruiters with 403."""

    method: str
    name: str
    args: tuple = ()
    query: str = ""
    data: dict = field(default_factory=dict)
    admin_only: bool = False

    def url(self):
        return reverse(self.name, args=self.args) + self.query

    def __str__(self):
        return f"{self.method.upper()} {self.url()}"


class ReviewData:
    """The data and the request table, shared with the accessibility review."""

    def setUp(self):
        super().setUp()
        self.admin = make_admin()
        self.recruiter = make_recruiter()
        self.target = make_recruiter("target")  # for staff actions
        self.inactive = make_recruiter("former", is_active=False)
        self.free_candidate = make_candidate("free@example.com")  # no applications
        self.archived = make_candidate("archived@example.com")
        archive_candidate(self.archived)
        self.open_job = make_job("Open job")
        self.empty_job = make_job("Empty job")  # no applications
        self.closed_job = make_job("Closed job")
        JobOpening.objects.filter(pk=self.closed_job.pk).update(status=JobStatus.CLOSED)
        self.application = make_application(job=self.open_job)  # never moved
        self.unused_skill = make_skill("Unused")
        self.used_skill = make_skill("Used")
        self.open_job.skills.add(self.used_skill)

    def cases(self):
        """The PRD permission table, one entry per page or action."""
        c, j, a = self.free_candidate, self.open_job, self.application
        candidate_data = {
            "first_name": "New",
            "last_name": "Person",
            "email": "new.person@example.com",
            "source": "referral",
        }
        job_data = {"title": "New job", "employment_type": "full_time", "work_mode": "remote"}
        return [
            # View dashboard, candidates, jobs, applications
            Case("get", "core:dashboard"),
            Case("get", "candidates:candidate_list"),
            Case("get", "candidates:candidate_archived_list"),
            Case("get", "candidates:candidate_detail", (c.pk,)),
            Case("get", "jobs:job_list"),
            Case("get", "jobs:job_list", query=f"?skill={self.used_skill.pk}"),
            Case("get", "jobs:job_detail", (j.pk,)),
            Case("get", "pipeline:application_list"),
            Case("get", "pipeline:application_list", query="?stage=applied"),
            Case("get", "pipeline:application_detail", (a.pk,)),
            Case("get", "pipeline:application_detail", (a.pk,), "?confirm=reject"),
            # Create and edit candidates; archive and restore
            Case("get", "candidates:candidate_create"),
            Case("post", "candidates:candidate_create", data=candidate_data),
            Case("get", "candidates:candidate_update", (c.pk,)),
            Case(
                "post",
                "candidates:candidate_update",
                (c.pk,),
                data=candidate_data | {"email": c.email},
            ),
            Case("post", "candidates:candidate_archive", (c.pk,)),
            Case("post", "candidates:candidate_restore", (self.archived.pk,)),
            # Create and edit jobs; assign skills; close and reopen
            Case("get", "jobs:job_create"),
            Case("post", "jobs:job_create", data=job_data | {"skills": [self.used_skill.pk]}),
            Case("get", "jobs:job_update", (j.pk,)),
            Case("post", "jobs:job_update", (j.pk,), data=job_data | {"skills": []}),
            Case("post", "jobs:job_close", (j.pk,)),
            Case("post", "jobs:job_reopen", (self.closed_job.pk,)),
            # Create applications; edit notes; Advance, Back, Reject, Withdraw, Reactivate
            Case("get", "pipeline:application_create"),
            Case("get", "pipeline:application_create", query=f"?candidate={c.pk}"),
            Case(
                "post",
                "pipeline:application_create",
                data={"candidate": c.pk, "job_opening": j.pk},
            ),
            Case("post", "pipeline:application_notes", (a.pk,), data={"notes": "Updated."}),
            Case(
                "post",
                "pipeline:application_transition",
                (a.pk,),
                data={"action": "advance", "expected_stage": "applied"},
            ),
            Case(
                "post",
                "pipeline:application_transition",
                (a.pk,),
                data={"action": "reject", "expected_stage": "applied", "note": "Not a fit."},
            ),
            Case(
                "post",
                "pipeline:application_transition",
                (a.pk,),
                data={"action": "withdraw", "expected_stage": "applied", "note": "Took a job."},
            ),
            # Create, rename and delete skills (Admin)
            Case("get", "jobs:skill_list", admin_only=True),
            Case("get", "jobs:skill_create", admin_only=True),
            Case("post", "jobs:skill_create", data={"name": "Go"}, admin_only=True),
            Case("get", "jobs:skill_update", (self.unused_skill.pk,), admin_only=True),
            Case(
                "post",
                "jobs:skill_update",
                (self.unused_skill.pk,),
                data={"name": "Renamed"},
                admin_only=True,
            ),
            Case("get", "jobs:skill_delete", (self.unused_skill.pk,), admin_only=True),
            Case("post", "jobs:skill_delete", (self.unused_skill.pk,), admin_only=True),
            # Permanently delete candidates, jobs, applications (Admin, subject to guards)
            Case("get", "candidates:candidate_delete", (c.pk,), admin_only=True),
            Case("post", "candidates:candidate_delete", (c.pk,), admin_only=True),
            Case("get", "jobs:job_delete", (self.empty_job.pk,), admin_only=True),
            Case("post", "jobs:job_delete", (self.empty_job.pk,), admin_only=True),
            Case("get", "pipeline:application_delete", (a.pk,), admin_only=True),
            Case("post", "pipeline:application_delete", (a.pk,), admin_only=True),
            # Create staff accounts, assign roles, deactivate and reactivate (Admin)
            Case("get", "staff:staff_list", admin_only=True),
            Case("get", "staff:staff_list", query="?show=inactive", admin_only=True),
            Case("get", "staff:staff_create", admin_only=True),
            Case(
                "post",
                "staff:staff_create",
                data={
                    "username": "nina",
                    "first_name": "Nina",
                    "last_name": "Simone",
                    "email": "nina@example.com",
                    "password1": NEW_PASSWORD,
                    "password2": NEW_PASSWORD,
                    "role": RECRUITER,
                },
                admin_only=True,
            ),
            Case(
                "post", "staff:staff_role", (self.target.pk,), data={"role": ADMIN}, admin_only=True
            ),
            Case("post", "staff:staff_deactivate", (self.target.pk,), admin_only=True),
            Case("post", "staff:staff_reactivate", (self.inactive.pk,), admin_only=True),
        ]


class PermissionReviewTests(ReviewData, TestCase):
    def request(self, case):
        """Send `case`, returning the response and whether the data changed, then roll back."""
        with transaction.atomic():
            before = database_state()
            response = getattr(self.client, case.method)(case.url(), case.data)
            changed = database_state() != before
            transaction.set_rollback(True)
        return response, changed

    def assertAllowed(self, case):
        response, changed = self.request(case)
        if case.method == "get":
            self.assertEqual(response.status_code, 200)
            self.assertFalse(changed, "a GET changed data")
        else:
            self.assertEqual(response.status_code, 302)
            self.assertTrue(changed, "an allowed POST changed nothing")

    def assertForbidden(self, case):
        response, changed = self.request(case)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(changed, "a forbidden request changed data")

    def test_the_table_covers_every_url_name(self):
        from django.urls import get_resolver

        covered = {case.name for case in self.cases()}
        resolver = get_resolver()
        names = {
            f"{namespace}:{name}"
            for namespace, (_, sub) in resolver.namespace_dict.items()
            for name in sub.reverse_dict
            if isinstance(name, str)
        }
        self.assertEqual(names - covered, set())

    def test_recruiter(self):
        self.client.force_login(self.recruiter)
        for case in self.cases():
            with self.subTest(case=str(case)):
                if case.admin_only:
                    self.assertForbidden(case)
                else:
                    self.assertAllowed(case)

    def test_admin_can_do_everything(self):
        self.client.force_login(self.admin)
        for case in self.cases():
            with self.subTest(case=str(case)):
                self.assertAllowed(case)

    def test_anonymous_is_redirected_to_login_and_nothing_changes(self):
        login = reverse("login")
        for case in self.cases():
            with self.subTest(case=str(case)):
                response, changed = self.request(case)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(f"{login}?next="))
                self.assertFalse(changed)

    def test_a_user_with_no_role_is_refused_everything(self):
        self.client.force_login(User.objects.create_user("nobody"))
        for case in self.cases():
            with self.subTest(case=str(case)):
                self.assertForbidden(case)

    def test_admin_navigation_renders_only_for_admins_on_every_page(self):
        pages = [case for case in self.cases() if case.method == "get"]
        admin_links = (reverse("jobs:skill_list"), reverse("staff:staff_list"))
        for user, expected in ((self.admin, True), (self.recruiter, False)):
            self.client.force_login(user)
            for case in pages:
                if case.admin_only and not expected:
                    continue
                with self.subTest(user=user.username, page=str(case)):
                    content = self.client.get(case.url()).content.decode()
                    nav = content.split('aria-label="Main navigation"')[1].split("</nav>")[0]
                    for link in admin_links:
                        self.assertEqual(f'href="{link}"' in nav, expected)
