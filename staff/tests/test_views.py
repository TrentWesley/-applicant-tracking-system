"""Phase 11: Staff Management pages (US 50-54; AC2, AC35-AC39)."""

from django.contrib.auth.models import Group, User
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from core.roles import ADMIN, RECRUITER, role_name
from core.tests.utils import PASSWORD, make_admin, make_recruiter, make_user
from pipeline.models import StageChange
from pipeline.services import change_stage
from pipeline.tests.utils import make_application
from staff.tests.utils import account_state

LIST_URL = reverse("staff:staff_list")
CREATE_URL = reverse("staff:staff_create")
NEW_PASSWORD = "plum-orchard-lantern-42"


def action_url(name, user):
    return reverse(f"staff:staff_{name}", args=[user.pk])


def make_manager():
    """
    Holds every Admin permission directly but has no Admin role, so it isn't an Admin itself.
    That's the only way someone other than the last active Admin can target them in one request.
    """
    manager = make_user("manager")
    manager.user_permissions.add(*Group.objects.get(name=ADMIN).permissions.all())
    return manager


def new_account(**overrides):
    data = {
        "username": "nina",
        "first_name": "Nina",
        "last_name": "Simone",
        "email": "nina@example.com",
        "password1": NEW_PASSWORD,
        "password2": NEW_PASSWORD,
        "role": RECRUITER,
    }
    return data | overrides


class StaffTestCase(TestCase):
    def setUp(self):
        self.admin = make_admin("ada", first_name="Ada", last_name="Lovelace")
        self.other_admin = make_admin("grace", first_name="Grace", last_name="Hopper")
        self.recruiter = make_recruiter("rita", first_name="Rita", last_name="Moreno")
        self.client.force_login(self.admin)

    def assertRefusedWithMessage(self, url, data, message):
        before = account_state()
        response = self.client.post(url, data, follow=True)
        self.assertContains(response, message)
        self.assertEqual(account_state(), before)
        return response


class StaffListTests(StaffTestCase):
    def test_lists_active_staff_with_their_roles(self):
        response = self.client.get(LIST_URL)
        self.assertTemplateUsed(response, "staff/staff_list.html")
        self.assertContains(response, "<h1", count=1)
        for name in ("Ada Lovelace", "Grace Hopper", "Rita Moreno"):
            self.assertContains(response, name)
        self.assertContains(response, ">Admin</span>", count=2)  # role badges
        self.assertContains(response, ">Recruiter</span>", count=1)

    def test_inactive_staff_are_hidden_by_default_and_shown_on_request(self):
        User.objects.filter(pk=self.recruiter.pk).update(is_active=False)
        self.assertNotContains(self.client.get(LIST_URL), "Rita Moreno")
        response = self.client.get(f"{LIST_URL}?show=inactive")
        self.assertContains(response, "Rita Moreno")
        self.assertContains(response, "Ada Lovelace")  # active staff are still listed
        self.assertContains(response, "Inactive")

    def test_your_own_row_has_no_deactivate_or_demote_button(self):
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, f'action="{action_url("deactivate", self.admin)}"')
        self.assertNotContains(response, f'action="{action_url("role", self.admin)}"')
        self.assertContains(response, f'action="{action_url("deactivate", self.other_admin)}"')
        self.assertContains(response, f'action="{action_url("role", self.other_admin)}"')

    def test_the_last_active_admin_has_no_deactivate_or_demote_button(self):
        User.objects.filter(pk=self.other_admin.pk).update(is_active=False)
        self.client.force_login(make_manager())
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, f'action="{action_url("deactivate", self.admin)}"')
        self.assertNotContains(response, f'action="{action_url("role", self.admin)}"')
        self.assertContains(response, f'action="{action_url("deactivate", self.recruiter)}"')

    def test_a_superuser_has_no_demote_button(self):
        root = make_user("root", is_superuser=True)
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, f'action="{action_url("role", root)}"')
        self.assertContains(response, f'action="{action_url("deactivate", root)}"')

    def test_actions_are_csrf_protected_post_forms(self):
        response = self.client.get(LIST_URL)
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_the_create_page_highlights_staff_management(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, f'href="{LIST_URL}" class="menu-active" aria-current="page"')


class StaffCreateTests(StaffTestCase):
    def test_admin_creates_a_recruiter(self):
        response = self.client.post(CREATE_URL, new_account(), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Staff account Nina Simone created as a Recruiter.")
        nina = User.objects.get(username="nina")
        self.assertEqual(list(nina.groups.values_list("name", flat=True)), [RECRUITER])
        self.assertEqual((nina.get_full_name(), nina.email), ("Nina Simone", "nina@example.com"))
        self.assertTrue(nina.check_password(NEW_PASSWORD))
        self.assertTrue(nina.is_active)
        self.assertFalse(nina.is_superuser or nina.is_staff)

    def test_admin_creates_an_admin(self):
        self.client.post(CREATE_URL, new_account(role=ADMIN))
        nina = User.objects.get(username="nina")
        self.assertEqual(list(nina.groups.values_list("name", flat=True)), [ADMIN])
        self.assertTrue(nina.has_perm("auth.change_user"))

    def test_the_new_account_can_log_in(self):
        self.client.post(CREATE_URL, new_account())
        self.client.logout()
        self.assertTrue(self.client.login(username="nina", password=NEW_PASSWORD))

    def test_the_form_has_labelled_fields(self):
        response = self.client.get(CREATE_URL)
        self.assertTemplateUsed(response, "staff/staff_form.html")
        for field in ("username", "first_name", "last_name", "email", "password1", "password2"):
            self.assertContains(response, f'for="id_{field}"')
        self.assertContains(response, 'for="id_role"')

    def test_every_field_is_required(self):
        response = self.client.post(CREATE_URL, {})
        form = response.context["form"]
        self.assertEqual(
            set(form.errors),
            {"username", "first_name", "last_name", "email", "password1", "password2", "role"},
        )
        self.assertFalse(User.objects.filter(username="").exists())

    def test_email_must_be_unique_ignoring_case(self):
        self.recruiter.email = "Rita@Example.com"
        self.recruiter.save()
        response = self.client.post(CREATE_URL, new_account(email="rita@example.COM"))
        self.assertFormError(
            response.context["form"], "email", "A staff account with this email already exists."
        )
        self.assertFalse(User.objects.filter(username="nina").exists())

    def test_username_must_be_unique_ignoring_case(self):
        response = self.client.post(CREATE_URL, new_account(username="RITA"))
        self.assertTrue(response.context["form"].has_error("username"))
        self.assertEqual(User.objects.count(), 3)

    def test_passwords_must_match_and_pass_the_validators(self):
        response = self.client.post(CREATE_URL, new_account(password2="something-else-99"))
        self.assertTrue(response.context["form"].has_error("password2"))
        response = self.client.post(CREATE_URL, new_account(password1="123", password2="123"))
        self.assertTrue(response.context["form"].has_error("password2"))
        self.assertFalse(User.objects.filter(username="nina").exists())

    def test_an_unknown_role_is_refused(self):
        response = self.client.post(CREATE_URL, new_account(role="Owner"))
        self.assertTrue(response.context["form"].has_error("role"))
        self.assertFalse(User.objects.filter(username="nina").exists())

    def test_a_superuser_flag_cannot_be_posted(self):
        self.client.post(CREATE_URL, new_account(is_superuser="on", is_staff="on"))
        nina = User.objects.get(username="nina")
        self.assertFalse(nina.is_superuser or nina.is_staff)


class DeactivateViewTests(StaffTestCase):
    def test_deactivating_a_recruiter(self):
        response = self.client.post(action_url("deactivate", self.recruiter), follow=True)
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Rita Moreno deactivated.")
        self.assertFalse(User.objects.get(pk=self.recruiter.pk).is_active)

    def test_deactivating_from_the_inactive_view_returns_there(self):
        response = self.client.post(action_url("deactivate", self.recruiter), {"show": "inactive"})
        self.assertRedirects(response, f"{LIST_URL}?show=inactive")

    def test_with_two_active_admins_deactivating_the_other_succeeds(self):
        self.client.post(action_url("deactivate", self.other_admin))
        self.assertFalse(User.objects.get(pk=self.other_admin.pk).is_active)

    def test_deactivating_yourself_by_direct_post_is_refused(self):
        self.assertRefusedWithMessage(
            action_url("deactivate", self.admin), {}, "You can&#x27;t deactivate your own account."
        )

    def test_deactivating_the_last_active_admin_by_direct_post_is_refused(self):
        User.objects.filter(pk=self.other_admin.pk).update(is_active=False)
        self.client.force_login(make_manager())
        self.assertRefusedWithMessage(
            action_url("deactivate", self.admin), {}, "Ada Lovelace is the last active Admin"
        )

    def test_a_repeated_deactivate_is_refused(self):
        self.client.post(action_url("deactivate", self.recruiter))
        self.assertRefusedWithMessage(
            action_url("deactivate", self.recruiter), {}, "Rita Moreno is already inactive"
        )

    def test_get_is_not_allowed(self):
        response = self.client.get(action_url("deactivate", self.recruiter))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(User.objects.get(pk=self.recruiter.pk).is_active)

    def test_unknown_account_is_404(self):
        for name in ("deactivate", "reactivate", "role"):
            with self.subTest(name=name):
                url = reverse(f"staff:staff_{name}", args=[999999])
                self.assertEqual(self.client.post(url, {"role": ADMIN}).status_code, 404)


class DeactivatedAccountTests(StaffTestCase):
    """AC36 and AC37: a deactivated user can't log in, and their history stays intact."""

    def setUp(self):
        super().setUp()
        self.application = make_application(created_by=self.recruiter)
        change_stage(
            application=self.application,
            action="advance",
            expected_stage="applied",
            changed_by=self.recruiter,
        )
        self.history = list(StageChange.objects.values_list())
        self.applications = list(self.application.__class__.objects.values_list())

    def assertHistoryUnchanged(self):
        self.assertEqual(list(StageChange.objects.values_list()), self.history)
        self.assertEqual(list(self.application.__class__.objects.values_list()), self.applications)

    def test_a_deactivated_user_cant_log_in(self):
        self.client.post(action_url("deactivate", self.recruiter))
        self.client.logout()
        self.assertFalse(self.client.login(username="rita", password=PASSWORD))
        response = self.client.post(reverse("login"), {"username": "rita", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)  # the login form again, with an error
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_a_signed_in_session_ends_when_the_account_is_deactivated(self):
        rita = self.client_class()
        rita.force_login(self.recruiter)
        self.client.post(action_url("deactivate", self.recruiter))
        response = rita.get(reverse("candidates:candidate_list"))
        self.assertRedirects(response, f"{reverse('login')}?next=/candidates/")

    def test_their_name_still_shows_on_application_and_history(self):
        self.client.post(action_url("deactivate", self.recruiter))
        response = self.client.get(self.application.get_absolute_url())
        self.assertContains(response, "by Rita Moreno")  # created by
        self.assertContains(response, "<td>Rita Moreno</td>", count=2)  # both history entries
        self.assertHistoryUnchanged()

    def test_reactivating_lets_them_log_in_with_history_unchanged(self):
        self.client.post(action_url("deactivate", self.recruiter))
        response = self.client.post(
            action_url("reactivate", self.recruiter), {"show": "inactive"}, follow=True
        )
        self.assertRedirects(response, f"{LIST_URL}?show=inactive")
        self.assertContains(response, "Rita Moreno reactivated. They can log in again.")
        self.client.logout()
        self.assertTrue(self.client.login(username="rita", password=PASSWORD))
        self.assertHistoryUnchanged()

    def test_a_repeated_reactivate_is_refused(self):
        self.assertRefusedWithMessage(
            action_url("reactivate", self.recruiter), {}, "Rita Moreno is already active"
        )

    def test_the_inactive_list_offers_reactivate(self):
        self.client.post(action_url("deactivate", self.recruiter))
        response = self.client.get(f"{LIST_URL}?show=inactive")
        self.assertContains(response, f'action="{action_url("reactivate", self.recruiter)}"')
        self.assertNotContains(response, f'action="{action_url("deactivate", self.recruiter)}"')


class RoleViewTests(StaffTestCase):
    def test_promoting_a_recruiter(self):
        response = self.client.post(
            action_url("role", self.recruiter), {"role": ADMIN}, follow=True
        )
        self.assertRedirects(response, LIST_URL)
        self.assertContains(response, "Rita Moreno is now an Admin.")
        self.assertEqual(role_name(self.recruiter), ADMIN)

    def test_with_two_active_admins_demoting_the_other_succeeds(self):
        response = self.client.post(
            action_url("role", self.other_admin), {"role": RECRUITER}, follow=True
        )
        self.assertContains(response, "Grace Hopper is now a Recruiter.")
        self.assertEqual(role_name(self.other_admin), RECRUITER)

    def test_demoting_yourself_by_direct_post_is_refused(self):
        self.assertRefusedWithMessage(
            action_url("role", self.admin),
            {"role": RECRUITER},
            "You can&#x27;t remove your own Admin role.",
        )

    def test_demoting_the_last_active_admin_by_direct_post_is_refused(self):
        User.objects.filter(pk=self.other_admin.pk).update(is_active=False)
        self.client.force_login(make_manager())
        self.assertRefusedWithMessage(
            action_url("role", self.admin), {"role": RECRUITER}, "is the last active Admin"
        )

    def test_a_repeated_or_missing_role_is_refused(self):
        self.assertRefusedWithMessage(
            action_url("role", self.recruiter), {"role": RECRUITER}, "already a Recruiter"
        )
        self.assertRefusedWithMessage(action_url("role", self.recruiter), {}, "Choose Admin or")


class RecruiterRefusalTests(TestCase):
    """AC2 and AC37: every staff page and action is 403 for a Recruiter, and nothing changes."""

    def test_recruiter_gets_403_everywhere_and_nothing_changes(self):
        admin = make_admin()
        recruiter = make_recruiter()
        User.objects.filter(pk=admin.pk).update(is_active=False)  # so Reactivate could apply
        self.client.force_login(recruiter)
        before = account_state()
        requests = [
            ("get", LIST_URL, {}),
            ("get", f"{LIST_URL}?show=inactive", {}),
            ("get", CREATE_URL, {}),
            ("post", CREATE_URL, new_account(role=ADMIN)),
            ("post", action_url("role", recruiter), {"role": ADMIN}),
            ("post", action_url("deactivate", recruiter), {}),
            ("post", action_url("reactivate", admin), {}),
        ]
        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url, data).status_code, 403)
        self.assertEqual(account_state(), before)

    def test_recruiter_sees_no_staff_management_link(self):
        self.client.force_login(make_recruiter())
        self.assertNotContains(self.client.get("/"), f'href="{LIST_URL}"')

    def test_anonymous_requests_are_redirected_to_login(self):
        recruiter = make_recruiter()
        for url in (LIST_URL, CREATE_URL, action_url("deactivate", recruiter)):
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")
        self.assertTrue(User.objects.get(pk=recruiter.pk).is_active)


class UserProtectTests(TestCase):
    """AC39: users referenced by an application or a stage change can't be deleted."""

    def test_deleting_a_user_on_an_application_or_stage_change_is_prevented(self):
        creator = make_recruiter("creator")
        mover = make_recruiter("mover")
        application = make_application(created_by=creator)
        change_stage(
            application=application, action="advance", expected_stage="applied", changed_by=mover
        )
        for user in (creator, mover):
            with self.subTest(user=user.username):
                with self.assertRaises(ProtectedError):
                    user.delete()
                self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(StageChange.objects.count(), 2)
