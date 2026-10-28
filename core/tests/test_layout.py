from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.utils import make_admin, make_recruiter

MAIN_NAV = {
    "Dashboard": "core:dashboard",
    "Candidates": "candidates:candidate_list",
    "Job Openings": "jobs:job_list",
    "Applications": "pipeline:application_list",
}
ADMIN_NAV = {
    "Skills": "jobs:skill_list",
    "Staff Management": "staff:staff_list",
}


class SidebarLayoutTests(TestCase):
    def get_dashboard(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_dashboard_uses_the_sidebar_layout(self):
        response = self.get_dashboard(make_recruiter())
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Dashboard</h1>")

    def test_drawer_toggle_has_an_accessible_label(self):
        response = self.get_dashboard(make_recruiter())
        self.assertContains(response, 'class="drawer lg:drawer-open')
        self.assertContains(response, 'id="nav-drawer"')
        self.assertContains(response, 'for="nav-drawer" aria-label="Open navigation menu"')
        self.assertContains(response, 'aria-label="Close navigation menu"')

    def test_drawer_columns_shrink_to_phone_width(self):
        # DaisyUI's drawer sizes the content column to max-content, so long text pushes the page
        # sideways at phone width (the UI prototype hit the same bug). A minmax(0,1fr) content
        # column lets it wrap.
        response = self.get_dashboard(make_recruiter())
        self.assertContains(
            response, 'class="drawer lg:drawer-open auto-cols-[max-content_minmax(0,1fr)]"'
        )

    def test_main_navigation_links_render_for_everyone(self):
        for user in (make_recruiter(), make_admin()):
            response = self.get_dashboard(user)
            for label, route in MAIN_NAV.items():
                with self.subTest(user=user.username, link=label):
                    self.assertContains(response, f'href="{reverse(route)}"')
                    self.assertContains(response, label)

    def test_current_page_is_marked_in_the_navigation(self):
        response = self.get_dashboard(make_recruiter())
        self.assertContains(
            response, f'href="{reverse("core:dashboard")}" class="menu-active" aria-current="page"'
        )

    def test_recruiter_does_not_see_admin_navigation(self):
        response = self.get_dashboard(make_recruiter())
        for label, route in ADMIN_NAV.items():
            with self.subTest(link=label):
                self.assertNotContains(response, f'href="{reverse(route)}"')
                self.assertNotContains(response, label)

    def test_admin_sees_admin_navigation(self):
        response = self.get_dashboard(make_admin())
        for label, route in ADMIN_NAV.items():
            with self.subTest(link=label):
                self.assertContains(response, f'href="{reverse(route)}"')
                self.assertContains(response, label)

    def test_superuser_sees_admin_navigation(self):
        response = self.get_dashboard(User.objects.create_superuser("root", password="x"))
        self.assertContains(response, f'href="{reverse("staff:staff_list")}"')

    def test_sidebar_shows_the_signed_in_user_and_role(self):
        response = self.get_dashboard(make_recruiter("rita", first_name="Rita", last_name="Ng"))
        self.assertContains(response, "Rita Ng")
        self.assertContains(response, ">Recruiter<")

        response = self.get_dashboard(make_admin("ada"))
        self.assertContains(response, "ada")
        self.assertContains(response, ">Admin<")

    def test_logout_is_a_post_form_with_csrf(self):
        response = self.get_dashboard(make_recruiter())
        self.assertContains(response, f'<form method="post" action="{reverse("logout")}"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_htmx_is_loaded_and_sends_the_csrf_token(self):
        response = self.get_dashboard(make_recruiter())
        self.assertContains(response, "js/htmx.min.js")
        token = response.context["csrf_token"]
        self.assertContains(response, f"""hx-headers='{{"X-CSRFToken": "{token}"}}'""")

    def test_tailwind_stylesheet_is_linked(self):
        response = self.get_dashboard(make_recruiter())
        self.assertContains(response, "css/tailwind.css")
        self.assertContains(response, 'name="viewport"')


class LoginPageLayoutTests(TestCase):
    def test_login_page_does_not_show_the_sidebar(self):
        response = self.client.get(reverse("login"))
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertNotContains(response, 'id="nav-drawer"')
        self.assertContains(response, '<label for="id_username"')
        self.assertContains(response, '<label for="id_password"')
