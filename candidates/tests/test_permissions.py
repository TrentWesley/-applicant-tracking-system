from django.contrib.auth.models import Group
from django.test import TestCase

from core.roles import ADMIN, RECRUITER
from core.tests.utils import make_admin, make_recruiter


def candidate_perms(group_name):
    return set(
        Group.objects.get(name=group_name)
        .permissions.filter(content_type__app_label="candidates")
        .values_list("codename", flat=True)
    )


class CandidatePermissionMigrationTests(TestCase):
    def test_recruiter_can_view_add_and_change_candidates(self):
        self.assertEqual(
            candidate_perms(RECRUITER), {"view_candidate", "add_candidate", "change_candidate"}
        )

    def test_admin_can_also_delete_candidates(self):
        self.assertEqual(
            candidate_perms(ADMIN),
            {"view_candidate", "add_candidate", "change_candidate", "delete_candidate"},
        )

    def test_permissions_apply_through_group_membership(self):
        recruiter, admin = make_recruiter(), make_admin()
        self.assertTrue(recruiter.has_perm("candidates.change_candidate"))
        self.assertFalse(recruiter.has_perm("candidates.delete_candidate"))
        self.assertTrue(admin.has_perm("candidates.delete_candidate"))
