from unittest import mock

from django.test import TestCase

from core.tests.utils import make_admin
from pipeline.models import Application, Stage, StageChange
from pipeline.services import (
    Action,
    StageChangeRefused,
    available_moves,
    change_stage,
)
from pipeline.tests.utils import make_application

ADVANCES = [
    (Stage.APPLIED, Stage.SCREENING),
    (Stage.SCREENING, Stage.INTERVIEW),
    (Stage.INTERVIEW, Stage.FINAL_REVIEW),
    (Stage.FINAL_REVIEW, Stage.OFFER),
    (Stage.OFFER, Stage.HIRED),
]
BACKS = [
    (Stage.SCREENING, Stage.APPLIED),
    (Stage.INTERVIEW, Stage.SCREENING),
    (Stage.FINAL_REVIEW, Stage.INTERVIEW),
    (Stage.OFFER, Stage.FINAL_REVIEW),
]


class TransitionTestCase(TestCase):
    def setUp(self):
        self.user = make_admin("mover")

    def move(self, application, action, expected_stage=None, **extra):
        return change_stage(
            application=application,
            action=action,
            expected_stage=application.stage if expected_stage is None else expected_stage,
            changed_by=self.user,
            **extra,
        )

    def assert_refused(self, application, action, message, **extra):
        before_stage, before_count = application.stage, StageChange.objects.count()
        before_changed_at = application.stage_changed_at
        with self.assertRaisesMessage(StageChangeRefused, message):
            self.move(application, action, **extra)
        application.refresh_from_db()
        self.assertEqual(application.stage, before_stage)
        self.assertEqual(application.stage_changed_at, before_changed_at)
        self.assertEqual(StageChange.objects.count(), before_count)


class AllowedMoveTests(TransitionTestCase):
    """AC21: every Advance and Back in the stage table writes exactly one correct StageChange."""

    def check_move(self, action, from_stage, to_stage, note=""):
        application = make_application(stage=from_stage)
        returned = self.move(application, action, note=note)
        self.assertEqual(application.stage, to_stage)  # refreshed in place
        application.refresh_from_db()
        self.assertEqual(application.stage, to_stage)
        entry = application.stage_changes.exclude(from_stage=None).get()
        self.assertEqual(returned, entry)
        self.assertEqual((entry.from_stage, entry.to_stage), (from_stage, to_stage))
        self.assertEqual(entry.changed_by, self.user)
        self.assertEqual(entry.note, note)
        self.assertEqual(application.stage_changed_at, entry.changed_at)
        self.assertEqual(application.stage_changes.count(), 2)  # creation entry + this move

    def test_every_advance(self):
        for from_stage, to_stage in ADVANCES:
            with self.subTest(from_stage=from_stage):
                self.check_move(Action.ADVANCE, from_stage, to_stage)

    def test_every_back(self):
        for from_stage, to_stage in BACKS:
            with self.subTest(from_stage=from_stage):
                self.check_move(Action.BACK, from_stage, to_stage)

    def test_an_optional_note_is_recorded_trimmed(self):
        self.check_move(Action.ADVANCE, Stage.APPLIED, Stage.SCREENING, note="Phone screen booked.")
        application = make_application(stage=Stage.INTERVIEW)
        self.move(application, Action.BACK, note="  Wrong round  ")
        self.assertEqual(application.stage_changes.last().note, "Wrong round")

    def test_action_may_be_given_as_its_posted_value(self):
        self.check_move("advance", Stage.APPLIED, Stage.SCREENING)

    def test_a_full_walk_to_hired_records_each_step_in_order(self):
        application = make_application()
        for _ in ADVANCES:
            self.move(application, Action.ADVANCE)
        self.assertEqual(application.stage, Stage.HIRED)
        self.assertEqual(
            [(c.from_stage, c.to_stage) for c in application.stage_changes.all()],
            [(None, Stage.APPLIED), *ADVANCES],
        )

    def test_moving_one_application_changes_no_other(self):
        application = make_application(stage=Stage.OFFER)
        other = make_application(job=application.job_opening, stage=Stage.OFFER)
        self.move(application, Action.ADVANCE)
        other.refresh_from_db()
        self.assertEqual(other.stage, Stage.OFFER)
        self.assertEqual(other.stage_changes.count(), 1)


class RefusedMoveTests(TransitionTestCase):
    """AC22: disallowed moves are refused and write nothing."""

    def test_back_from_applied(self):
        self.assert_refused(make_application(), Action.BACK, "Back isn't allowed from Applied.")

    def test_nothing_moves_hired_which_is_permanent(self):
        for action in Action:
            with self.subTest(action=action):
                self.assert_refused(
                    make_application(stage=Stage.HIRED), action, "Hired is permanent"
                )

    def test_advance_and_back_from_rejected_and_withdrawn(self):
        for stage in (Stage.REJECTED, Stage.WITHDRAWN):
            for action in Action:
                with self.subTest(stage=stage, action=action):
                    self.assert_refused(
                        make_application(stage=stage),
                        action,
                        f"{action.label} isn't allowed from {stage.label}.",
                    )

    def test_unknown_actions_are_refused(self):
        for action in ("", "hire", "skip", "jump_to_offer", "ADVANCE"):
            with self.subTest(action=action):
                self.assert_refused(
                    make_application(), action, "That stage action isn't recognised."
                )

    def test_there_is_no_way_to_name_a_target_stage(self):
        # The service only takes an action; the next stage always comes from the table.
        application = make_application()
        with self.assertRaises(TypeError):
            change_stage(
                application=application,
                action=Action.ADVANCE,
                expected_stage=Stage.APPLIED,
                changed_by=self.user,
                to_stage=Stage.HIRED,
            )
        self.assertEqual(StageChange.objects.count(), 1)


class StaleAndDoubleClickTests(TransitionTestCase):
    def test_stale_expected_stage_is_refused_as_already_updated(self):
        application = make_application(stage=Stage.INTERVIEW)
        self.assert_refused(
            application,
            Action.ADVANCE,
            "This application was already updated",
            expected_stage=Stage.SCREENING,
        )

    def test_the_stale_check_comes_before_the_allowed_check(self):
        # Back is never allowed from Applied, but the screen is out of date: say so first.
        application = make_application(stage=Stage.SCREENING)
        self.assert_refused(
            application,
            Action.BACK,
            "This application was already updated",
            expected_stage=Stage.APPLIED,
        )

    def test_the_refusal_names_the_current_stage(self):
        application = make_application(stage=Stage.OFFER)
        self.assert_refused(
            application, Action.ADVANCE, "It's now at Offer.", expected_stage=Stage.APPLIED
        )

    def test_a_double_click_moves_exactly_once(self):
        # AC28: both requests carry the same expected stage.
        application = make_application()
        self.move(application, Action.ADVANCE, expected_stage=Stage.APPLIED)
        self.assert_refused(
            Application.objects.get(pk=application.pk),
            Action.ADVANCE,
            "already updated",
            expected_stage=Stage.APPLIED,
        )
        application.refresh_from_db()
        self.assertEqual(application.stage, Stage.SCREENING)
        self.assertEqual(application.stage_changes.count(), 2)

    def test_a_move_committed_after_the_stale_check_is_caught_by_the_conditional_update(self):
        # Another request moved the application after this one read the stage: the read still
        # says Applied, but the UPDATE … WHERE stage = 'applied' matches no row.
        application = make_application()
        Application.objects.filter(pk=application.pk).update(stage=Stage.SCREENING)
        application.refresh_from_db()
        with mock.patch("pipeline.services.current_stage", return_value=Stage.APPLIED):
            self.assert_refused(
                application, Action.ADVANCE, "already updated", expected_stage=Stage.APPLIED
            )
        application.refresh_from_db()
        self.assertEqual(application.stage, Stage.SCREENING)


class AvailableMovesTests(TestCase):
    """The card renders exactly these; Phase 6 adds Reject, Withdraw and Reactivate."""

    def test_moves_for_each_of_the_eight_stages(self):
        expected = {
            Stage.APPLIED: [(Action.ADVANCE, Stage.SCREENING)],
            Stage.SCREENING: [(Action.ADVANCE, Stage.INTERVIEW), (Action.BACK, Stage.APPLIED)],
            Stage.INTERVIEW: [(Action.ADVANCE, Stage.FINAL_REVIEW), (Action.BACK, Stage.SCREENING)],
            Stage.FINAL_REVIEW: [(Action.ADVANCE, Stage.OFFER), (Action.BACK, Stage.INTERVIEW)],
            Stage.OFFER: [(Action.ADVANCE, Stage.HIRED), (Action.BACK, Stage.FINAL_REVIEW)],
            Stage.HIRED: [],
            Stage.REJECTED: [],
            Stage.WITHDRAWN: [],
        }
        for stage, moves in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual([(m.action, m.target) for m in available_moves(stage)], moves)

    def test_accepts_the_plain_string_stored_in_the_database(self):
        self.assertEqual(len(available_moves("screening")), 2)
