from django.test import TestCase
from django.urls import reverse

from core.tests.utils import PASSWORD, make_recruiter

PROTECTED_URLS = ["/", "/candidates/", "/jobs/", "/applications/", "/skills/", "/staff/"]


class AnonymousAccessTests(TestCase):
    def test_every_page_redirects_anonymous_users_to_login(self):
        for url in PROTECTED_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"/accounts/login/?next={url}", fetch_redirect_response=False
                )

    def test_login_page_is_reachable_anonymously(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, "csrfmiddlewaretoken")


class LoginTests(TestCase):
    def test_valid_credentials_log_in_and_land_on_dashboard(self):
        make_recruiter("rita")
        response = self.client.post(
            reverse("login"), {"username": "rita", "password": PASSWORD}, follow=True
        )
        self.assertRedirects(response, reverse("core:dashboard"))
        self.assertTrue(response.context["user"].is_authenticated)

    def test_login_honours_next_parameter(self):
        make_recruiter("rita")
        response = self.client.post(
            reverse("login") + "?next=/jobs/", {"username": "rita", "password": PASSWORD}
        )
        self.assertRedirects(response, "/jobs/", fetch_redirect_response=False)

    def test_wrong_password_is_refused(self):
        make_recruiter("rita")
        response = self.client.post(reverse("login"), {"username": "rita", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertTrue(response.context["form"].errors)

    def test_inactive_user_cannot_log_in(self):
        make_recruiter("gone", is_active=False)
        response = self.client.post(reverse("login"), {"username": "gone", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertNotIn("_auth_user_id", self.client.session)


class LogoutTests(TestCase):
    def test_logout_by_post_returns_to_login(self):
        self.client.force_login(make_recruiter())
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_by_get_is_not_allowed(self):
        self.client.force_login(make_recruiter())
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
