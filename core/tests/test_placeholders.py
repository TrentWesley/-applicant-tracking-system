from django.test import TestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter

SHARED_PAGES = ["candidates:candidate_list", "jobs:job_list", "pipeline:application_list"]
ADMIN_PAGES = ["jobs:skill_list", "staff:staff_list"]


class SectionPageAccessTests(TestCase):
    """Navigation targets exist now; later phases replace their content."""

    def test_recruiter_can_open_shared_pages(self):
        self.client.force_login(make_recruiter())
        for route in SHARED_PAGES:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")

    def test_recruiter_is_forbidden_from_admin_pages(self):
        self.client.force_login(make_recruiter())
        for route in ADMIN_PAGES:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_admin_can_open_every_page(self):
        self.client.force_login(make_admin())
        for route in SHARED_PAGES + ADMIN_PAGES:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_section_pages_mark_themselves_current(self):
        self.client.force_login(make_admin())
        for route in SHARED_PAGES + ADMIN_PAGES:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertContains(
                    response, f'href="{reverse(route)}" class="menu-active" aria-current="page"'
                )
