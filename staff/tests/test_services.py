"""Phase 11: the staff service (US 51-53; AC36-AC38). Each refusal changes nothing."""

from django.contrib.auth.models import User
from django.test import TestCase

from core.roles import ADMIN, RECRUITER, role_name
from core.tests.utils import make_admin, make_recruiter, make_user
from staff.services import StaffChangeRefused, change_role, deactivate_staff, reactivate_staff
from staff.tests.utils import account_state


class ServiceTestCase(TestCase):
    def setUp(self):
        self.admin = make_admin("ada", first_name="Ada", last_name="Lovelace")
        self.other_admin = make_admin("grace", first_name="Grace", last_name="Hopper")
        self.recruiter = make_recruiter("rita", first_name="Rita", last_name="Moreno")

    def assertRefused(self, call, message):
        before = account_state()
        with self.assertRaisesMessage(StaffChangeRefused, message):
            call()
        self.assertEqual(account_state(), before)


class DeactivateTests(ServiceTestCase):
    def test_deactivating_changes_only_is_active(self):
        before = account_state()[self.recruiter.pk]
        deactivate_staff(self.recruiter, by=self.admin)
        self.assertFalse(self.recruiter.is_active)  # refreshed in place
        self.assertEqual(account_state()[self.recruiter.pk], (False, *before[1:]))

    def test_an_admin_can_deactivate_another_admin(self):
        deactivate_staff(self.other_admin, by=self.admin)
        self.assertFalse(User.objects.get(pk=self.other_admin.pk).is_active)

    def test_deactivating_yourself_is_refused(self):
        self.assertRefused(
            lambda: deactivate_staff(self.admin, by=self.admin),
            "You can't deactivate your own account.",
        )

    def test_deactivating_the_last_active_admin_is_refused(self):
        # Someone else can only try this with the staff permissions but without the Admin role
        # (or from a request that started before their own account changed).
        deactivate_staff(self.other_admin, by=self.admin)
        manager = make_user("manager")
        self.assertRefused(
            lambda: deactivate_staff(self.admin, by=manager),
            "Ada Lovelace is the last active Admin, so they can't be deactivated.",
        )

    def test_an_inactive_admin_does_not_count(self):
        User.objects.filter(pk=self.other_admin.pk).update(is_active=False)
        manager = make_user("manager")
        self.assertRefused(
            lambda: deactivate_staff(self.admin, by=manager),
            "is the last active Admin",
        )

    def test_an_active_superuser_counts_as_another_admin(self):
        User.objects.filter(pk=self.other_admin.pk).update(is_active=False)
        make_user("root", is_superuser=True)
        deactivate_staff(self.admin, by=make_user("manager"))
        self.assertFalse(User.objects.get(pk=self.admin.pk).is_active)

    def test_a_repeated_deactivate_is_refused(self):
        deactivate_staff(self.recruiter, by=self.admin)
        self.assertRefused(
            lambda: deactivate_staff(self.recruiter, by=self.admin),
            "Rita Moreno is already inactive, so nothing was changed.",
        )

    def test_a_stale_copy_is_checked_against_the_stored_account(self):
        stale = User.objects.get(pk=self.recruiter.pk)
        deactivate_staff(self.recruiter, by=self.admin)
        self.assertRefused(lambda: deactivate_staff(stale, by=self.admin), "already inactive")


class ReactivateTests(ServiceTestCase):
    def test_reactivating_changes_only_is_active(self):
        deactivate_staff(self.recruiter, by=self.admin)
        before = account_state()[self.recruiter.pk]
        reactivate_staff(self.recruiter)
        self.assertTrue(self.recruiter.is_active)
        self.assertEqual(account_state()[self.recruiter.pk], (True, *before[1:]))

    def test_a_repeated_reactivate_is_refused(self):
        self.assertRefused(
            lambda: reactivate_staff(self.recruiter),
            "Rita Moreno is already active, so nothing was changed.",
        )

    def test_a_stale_reactivate_is_refused(self):
        deactivate_staff(self.recruiter, by=self.admin)
        stale = User.objects.get(pk=self.recruiter.pk)
        reactivate_staff(self.recruiter)
        self.assertRefused(lambda: reactivate_staff(stale), "already active")


class ChangeRoleTests(ServiceTestCase):
    def test_promoting_a_recruiter_makes_them_only_an_admin(self):
        change_role(self.recruiter, ADMIN, by=self.admin)
        self.assertEqual(list(self.recruiter.groups.values_list("name", flat=True)), [ADMIN])
        self.assertTrue(self.recruiter.has_perm("auth.change_user"))

    def test_with_two_active_admins_demoting_the_other_succeeds(self):
        change_role(self.other_admin, RECRUITER, by=self.admin)
        self.assertEqual(list(self.other_admin.groups.values_list("name", flat=True)), [RECRUITER])
        self.assertFalse(User.objects.get(pk=self.other_admin.pk).has_perm("auth.change_user"))

    def test_an_account_with_no_role_can_be_given_one(self):
        nobody = make_user("nobody")
        change_role(nobody, RECRUITER, by=self.admin)
        self.assertEqual(role_name(nobody), RECRUITER)

    def test_only_the_role_changes(self):
        before = account_state()[self.recruiter.pk]
        change_role(self.recruiter, ADMIN, by=self.admin)
        after = account_state()[self.recruiter.pk]
        self.assertEqual((after[:2], after[3:]), (before[:2], before[3:]))

    def test_demoting_yourself_is_refused(self):
        self.assertRefused(
            lambda: change_role(self.admin, RECRUITER, by=self.admin),
            "You can't remove your own Admin role.",
        )

    def test_demoting_the_last_active_admin_is_refused(self):
        deactivate_staff(self.other_admin, by=self.admin)
        manager = make_user("manager")
        self.assertRefused(
            lambda: change_role(self.admin, RECRUITER, by=manager),
            "Ada Lovelace is the last active Admin, so they can't be made a Recruiter.",
        )

    def test_demoting_an_inactive_admin_is_allowed(self):
        deactivate_staff(self.other_admin, by=self.admin)
        change_role(self.other_admin, RECRUITER, by=self.admin)
        self.assertEqual(role_name(self.other_admin), RECRUITER)

    def test_a_superuser_cant_be_demoted(self):
        root = make_user("root", is_superuser=True)
        self.assertRefused(
            lambda: change_role(root, RECRUITER, by=self.admin),
            "root is a superuser, so they're always an Admin.",
        )

    def test_a_repeated_role_change_is_refused(self):
        self.assertRefused(
            lambda: change_role(self.recruiter, RECRUITER, by=self.admin),
            "Rita Moreno is already a Recruiter, so nothing was changed.",
        )
        self.assertRefused(
            lambda: change_role(self.other_admin, ADMIN, by=self.admin),
            "Grace Hopper is already an Admin, so nothing was changed.",
        )

    def test_an_unknown_role_is_refused(self):
        self.assertRefused(
            lambda: change_role(self.recruiter, "Owner", by=self.admin),
            "Choose Admin or Recruiter.",
        )
