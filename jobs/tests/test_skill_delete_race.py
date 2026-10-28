from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import Collector
from django.test import TransactionTestCase
from django.urls import reverse

from core.tests.utils import make_admin
from jobs.models import JobSkill, Skill
from jobs.tests.utils import make_job, make_skill


def collect_without_seeing_assignments(collector, objs, *args, **kwargs):
    """
    Stand-in for Collector.collect that skips the PROTECT lookup, as if that lookup ran just
    before another request committed a new job-skill assignment.
    """
    collector.add(objs)


class SkillDeleteRaceTests(TransactionTestCase):
    """
    These tests commit for real, so the database's deferred foreign-key check runs. In a
    TestCase everything stays inside one uncommitted transaction and that check never fires.
    """

    serialized_rollback = True  # restore the migration-created role groups afterwards

    def setUp(self):
        self.skill = make_skill("Python")
        self.job = make_job("Data Analyst")

    def test_database_refuses_to_delete_a_skill_that_a_job_still_uses(self):
        JobSkill.objects.create(job=self.job, skill=self.skill)
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM jobs_skill WHERE id = %s", [self.skill.pk])
        self.assertEqual(list(self.job.skills.all()), [self.skill])

    def test_database_refuses_to_assign_a_skill_that_was_just_deleted(self):
        skill_pk = self.skill.pk
        self.skill.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            JobSkill.objects.create(job=self.job, skill_id=skill_pk)
        self.assertFalse(self.job.skills.exists())

    def test_assignment_committed_after_the_check_still_blocks_the_delete(self):
        # Another request assigned the skill after this delete's PROTECT lookup found nothing.
        JobSkill.objects.create(job=self.job, skill=self.skill)
        self.client.force_login(make_admin())
        url = reverse("jobs:skill_delete", args=[self.skill.pk])
        with mock.patch.object(Collector, "collect", collect_without_seeing_assignments):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "can't be deleted")
        self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())
        self.assertEqual(list(self.job.skills.all()), [self.skill])
