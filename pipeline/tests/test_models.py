from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from candidates.tests.utils import make_candidate
from core.tests.utils import make_recruiter
from jobs.tests.utils import make_job
from pipeline.models import (
    ACTIVE_STAGES,
    TERMINAL_STAGES,
    Application,
    HistoryIsImmutable,
    Stage,
    StageChange,
)


def make_row(candidate=None, job=None, user=None, **extra):
    """An Application written straight to the database; the service comes in cycle 3."""
    fields = {
        "candidate": candidate or make_candidate(),
        "job_opening": job or make_job(),
        "created_by": user or make_recruiter(),
        "stage_changed_at": timezone.now(),
    } | extra
    return Application.objects.create(**fields)


class StageTests(TestCase):
    def test_the_eight_stages_in_pipeline_order(self):
        self.assertEqual(
            Stage.labels,
            [
                "Applied",
                "Screening",
                "Interview",
                "Final Review",
                "Offer",
                "Hired",
                "Rejected",
                "Withdrawn",
            ],
        )

    def test_five_active_and_three_terminal_stages(self):
        self.assertEqual(
            ACTIVE_STAGES,
            (Stage.APPLIED, Stage.SCREENING, Stage.INTERVIEW, Stage.FINAL_REVIEW, Stage.OFFER),
        )
        self.assertEqual(TERMINAL_STAGES, (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN))

    def test_each_stage_knows_whether_it_is_active(self):
        self.assertTrue(Stage.OFFER.is_active)
        self.assertFalse(Stage.HIRED.is_active)
        self.assertFalse(Stage.WITHDRAWN.is_active)


class ApplicationModelTests(TestCase):
    def test_a_new_row_defaults_to_applied(self):
        self.assertEqual(make_row().stage, Stage.APPLIED)

    def test_stage_and_creator_are_not_editable_on_forms(self):
        for name in ("stage", "stage_changed_at", "created_by"):
            with self.subTest(field=name):
                self.assertFalse(Application._meta.get_field(name).editable)

    def test_a_candidate_job_pair_is_unique_at_the_database_level(self):
        candidate, job = make_candidate(), make_job()
        make_row(candidate, job)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_row(candidate, job, user=make_recruiter("other"))
        self.assertEqual(Application.objects.count(), 1)

    def test_the_same_candidate_may_apply_to_another_job(self):
        candidate = make_candidate()
        make_row(candidate, make_job("Analyst"))
        make_row(candidate, make_job("Engineer"), user=make_recruiter("other"))
        self.assertEqual(candidate.applications.count(), 2)

    def test_candidate_job_and_creator_are_protected_from_deletion(self):
        application = make_row()
        for related in (application.candidate, application.job_opening, application.created_by):
            with self.subTest(model=type(related).__name__), self.assertRaises(ProtectedError):
                related.delete()
        self.assertTrue(Application.objects.filter(pk=application.pk).exists())

    def test_str_and_absolute_url(self):
        application = make_row(
            make_candidate(first_name="Ann", last_name="Lee"), make_job("Analyst")
        )
        self.assertEqual(str(application), "Ann Lee for Analyst")
        self.assertEqual(application.get_absolute_url(), f"/applications/{application.pk}/")


class StageChangeModelTests(TestCase):
    def setUp(self):
        self.application = make_row()
        self.user = self.application.created_by

    def add_change(self, **extra):
        fields = {
            "application": self.application,
            "from_stage": None,
            "to_stage": Stage.APPLIED,
            "changed_by": self.user,
        } | extra
        return StageChange.objects.create(**fields)

    def test_creation_entry_has_no_from_stage(self):
        change = self.add_change()
        change.refresh_from_db()
        self.assertIsNone(change.from_stage)
        self.assertEqual(change.note, "")
        self.assertIsNotNone(change.changed_at)

    def test_history_is_ordered_oldest_first(self):
        now = timezone.now()
        later = self.add_change(from_stage=Stage.APPLIED, to_stage=Stage.SCREENING, changed_at=now)
        first = self.add_change(changed_at=now - timezone.timedelta(days=1))
        same_time = self.add_change(
            from_stage=Stage.SCREENING, to_stage=Stage.INTERVIEW, changed_at=now
        )
        self.assertEqual(list(self.application.stage_changes.all()), [first, later, same_time])

    def test_changer_is_protected_from_deletion(self):
        # A different user from the application's creator, so only StageChange protects them.
        changer = make_recruiter("changer")
        self.add_change(changed_by=changer)
        with self.assertRaises(ProtectedError):
            changer.delete()


class StageChangeImmutabilityTests(TestCase):
    """History is append-only: rows are added, never changed, and go only with their application."""

    def setUp(self):
        self.application = make_row()
        self.change = StageChange.objects.create(
            application=self.application,
            to_stage=Stage.APPLIED,
            changed_by=self.application.created_by,
            note="Original note",
        )

    def assert_unchanged(self):
        self.change.refresh_from_db()
        self.assertEqual(self.change.note, "Original note")
        self.assertEqual(self.change.to_stage, Stage.APPLIED)

    def test_saving_an_existing_row_is_refused(self):
        self.change.note = "Rewritten"
        with self.assertRaises(HistoryIsImmutable):
            self.change.save()
        self.assert_unchanged()

    def test_deleting_a_row_is_refused(self):
        with self.assertRaises(HistoryIsImmutable):
            self.change.delete()
        self.assertTrue(StageChange.objects.filter(pk=self.change.pk).exists())

    def test_queryset_update_and_delete_are_refused(self):
        with self.assertRaises(HistoryIsImmutable):
            StageChange.objects.filter(pk=self.change.pk).update(note="Rewritten")
        with self.assertRaises(HistoryIsImmutable):
            StageChange.objects.all().delete()
        self.assert_unchanged()

    def test_the_database_refuses_updates_that_bypass_the_orm(self):
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE pipeline_stagechange SET note = 'Rewritten' WHERE id = %s", [self.change.pk]
            )
        self.assert_unchanged()

    def test_bulk_update_is_refused(self):
        self.change.note = "Rewritten"
        with self.assertRaises(HistoryIsImmutable):
            StageChange.objects.bulk_update([self.change], ["note"])
        self.assert_unchanged()

    def test_a_new_instance_reusing_an_existing_id_cannot_overwrite_it(self):
        # Django saves an instance that has a pk with an UPDATE first, even when it's "new", so
        # only the database trigger stops this one.
        impostor = StageChange(
            pk=self.change.pk,
            application=self.application,
            to_stage=Stage.HIRED,
            changed_by=self.application.created_by,
            note="Rewritten",
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            impostor.save()
        self.assert_unchanged()

    def test_deleting_the_application_removes_its_history(self):
        # Phase 10 lets an Admin delete a never-moved application along with its creation entry.
        self.application.delete()
        self.assertFalse(StageChange.objects.exists())
