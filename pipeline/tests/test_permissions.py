from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from core.roles import ADMIN, RECRUITER
from core.tests.utils import make_admin, make_recruiter


def pipeline_perms(group_name):
    return set(
        Group.objects.get(name=group_name)
        .permissions.filter(content_type__app_label="pipeline")
        .values_list("codename", flat=True)
    )


class PipelinePermissionMigrationTests(TestCase):
    def test_recruiter_can_view_add_and_change_applications(self):
        self.assertEqual(
            pipeline_perms(RECRUITER),
            {"view_application", "add_application", "change_application"},
        )

    def test_admin_can_also_delete_applications(self):
        self.assertEqual(
            pipeline_perms(ADMIN),
            {"view_application", "add_application", "change_application", "delete_application"},
        )

    def test_stage_history_has_no_permissions_to_grant(self):
        # No screen creates, edits or deletes a StageChange; only the service writes them.
        self.assertFalse(Permission.objects.filter(content_type__model="stagechange").exists())

    def test_permissions_apply_through_group_membership(self):
        recruiter, admin = make_recruiter(), make_admin()
        self.assertTrue(recruiter.has_perm("pipeline.add_application"))
        self.assertFalse(recruiter.has_perm("pipeline.delete_application"))
        self.assertTrue(admin.has_perm("pipeline.delete_application"))
