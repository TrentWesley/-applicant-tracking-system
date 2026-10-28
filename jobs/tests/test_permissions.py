from django.contrib.auth.models import Group
from django.test import TestCase

from core.roles import ADMIN, RECRUITER
from core.tests.utils import make_admin, make_recruiter


def job_app_perms(group_name):
    return set(
        Group.objects.get(name=group_name)
        .permissions.filter(content_type__app_label="jobs")
        .values_list("codename", flat=True)
    )


class JobsPermissionMigrationTests(TestCase):
    def test_recruiter_can_manage_jobs_but_only_view_skills(self):
        self.assertEqual(
            job_app_perms(RECRUITER),
            {"view_jobopening", "add_jobopening", "change_jobopening", "view_skill"},
        )

    def test_admin_can_also_delete_jobs_and_manage_skills(self):
        self.assertEqual(
            job_app_perms(ADMIN),
            {
                "view_jobopening",
                "add_jobopening",
                "change_jobopening",
                "delete_jobopening",
                "view_skill",
                "add_skill",
                "change_skill",
                "delete_skill",
            },
        )

    def test_permissions_apply_through_group_membership(self):
        recruiter, admin = make_recruiter(), make_admin()
        self.assertTrue(recruiter.has_perm("jobs.change_jobopening"))
        self.assertFalse(recruiter.has_perm("jobs.delete_jobopening"))
        self.assertFalse(recruiter.has_perm("jobs.add_skill"))
        self.assertTrue(admin.has_perm("jobs.delete_skill"))
