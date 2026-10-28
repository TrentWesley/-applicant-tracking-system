from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.test import TestCase

from core.roles import ADMIN, RECRUITER, grant_permissions, is_admin, role_name
from core.tests.utils import make_admin, make_recruiter, make_user


def group_perms(name):
    return set(
        Group.objects.get(name=name).permissions.values_list("content_type__app_label", "codename")
    )


class GroupMigrationTests(TestCase):
    """The groups and their permissions come from migrations, so a fresh database has them."""

    def test_both_groups_exist_after_migrating(self):
        self.assertEqual(
            set(Group.objects.filter(name__in=[RECRUITER, ADMIN]).values_list("name", flat=True)),
            {RECRUITER, ADMIN},
        )

    def test_admin_has_user_permissions_for_staff_management(self):
        self.assertEqual(
            group_perms(ADMIN),
            {("auth", "view_user"), ("auth", "add_user"), ("auth", "change_user")},
        )

    def test_admin_cannot_delete_users(self):
        # Staff accounts are deactivated, never deleted.
        self.assertNotIn(("auth", "delete_user"), group_perms(ADMIN))

    def test_recruiter_has_no_user_permissions(self):
        self.assertEqual(group_perms(RECRUITER), set())

    def test_group_membership_grants_the_permission(self):
        self.assertTrue(make_admin().has_perm("auth.change_user"))
        self.assertFalse(make_recruiter().has_perm("auth.change_user"))


class GrantPermissionsTests(TestCase):
    """
    Django only creates model permissions in a post_migrate signal, after every migration has
    run. On a fresh database a data migration therefore can't look them up; grant_permissions
    must create any that are missing first.
    """

    def setUp(self):
        Permission.objects.filter(
            content_type__app_label="auth", content_type__model="user"
        ).delete()
        self.group = Group.objects.create(name="Testers")

    def test_creates_missing_permissions_and_assigns_them(self):
        grant_permissions(global_apps, "Testers", "auth", "user", ["view", "change"])
        self.assertEqual(group_perms("Testers"), {("auth", "view_user"), ("auth", "change_user")})
        self.assertEqual(Permission.objects.get(codename="change_user").name, "Can change user")

    def test_is_idempotent(self):
        grant_permissions(global_apps, "Testers", "auth", "user", ["view"])
        grant_permissions(global_apps, "Testers", "auth", "user", ["view"])
        self.assertEqual(Permission.objects.filter(codename="view_user").count(), 1)
        self.assertEqual(self.group.permissions.count(), 1)

    def test_post_migrate_signal_does_not_duplicate_them(self):
        grant_permissions(global_apps, "Testers", "auth", "user", ["view", "add", "change"])
        create_permissions(global_apps.get_app_config("auth"), verbosity=0)
        self.assertEqual(
            Permission.objects.filter(
                content_type__app_label="auth", content_type__model="user"
            ).count(),
            4,
        )
        self.assertEqual(self.group.permissions.count(), 3)


class RoleHelperTests(TestCase):
    def test_admin_group_member_is_admin(self):
        user = make_admin()
        self.assertTrue(is_admin(user))
        self.assertEqual(role_name(user), "Admin")

    def test_recruiter_is_not_admin(self):
        user = make_recruiter()
        self.assertFalse(is_admin(user))
        self.assertEqual(role_name(user), "Recruiter")

    def test_superuser_counts_as_admin(self):
        user = User.objects.create_superuser("root", password="x")
        self.assertTrue(is_admin(user))
        self.assertEqual(role_name(user), "Admin")

    def test_user_without_a_group_has_no_role(self):
        user = make_user("nobody")
        self.assertFalse(is_admin(user))
        self.assertEqual(role_name(user), "")

    def test_anonymous_user_is_not_admin(self):
        self.assertFalse(is_admin(AnonymousUser()))
        self.assertEqual(role_name(AnonymousUser()), "")
