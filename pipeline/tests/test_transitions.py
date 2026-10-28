from unittest import mock

from django.test import TestCase
from django.utils import timezone

from candidates.models import Candidate
from core.tests.utils import make_admin
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import ACTIVE_STAGES, Application, Stage, StageChange
from pipeline.services import (
    Action,
    Move,
    NoteRequired,
    StageChangeRefused,
    available_moves,
    change_stage,
    reactivation_target,
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
EXITS = [(Action.REJECT, Stage.REJECTED), (Action.WITHDRAW, Stage.WITHDRAWN)]
NOTE = "Not a fit for the role."


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


class AllowedMoveTests(TransitionTestCase):
    """AC21: every Advance and Back in the stage table writes exactly one correct StageChange."""

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

    def test_nothing_moves_hired_even_with_a_note(self):
        # AC25 (Hired part): Reactivate included; the note doesn't matter.
        for action in Action:
            with self.subTest(action=action):
                self.assert_refused(
                    make_application(stage=Stage.HIRED), action, "Hired is permanent", note=NOTE
                )

    def test_only_reactivate_leaves_rejected_and_withdrawn(self):
        for stage in (Stage.REJECTED, Stage.WITHDRAWN):
            for action in (Action.ADVANCE, Action.BACK, Action.REJECT, Action.WITHDRAW):
                with self.subTest(stage=stage, action=action):
                    self.assert_refused(
                        make_application(stage=stage),
                        action,
                        f"{action.label} isn't allowed from {stage.label}.",
                        note=NOTE,
                    )

    def test_reactivate_from_an_active_stage(self):
        for stage in ACTIVE_STAGES:
            with self.subTest(stage=stage):
                self.assert_refused(
                    make_application(stage=stage),
                    Action.REACTIVATE,
                    f"Reactivate isn't allowed from {stage.label}.",
                    note=NOTE,
                )

    def test_the_allowed_check_comes_before_the_note_check(self):
        self.assert_refused(
            make_application(stage=Stage.REJECTED), Action.REJECT, "Reject isn't allowed"
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


class ExitMoveTests(TransitionTestCase):
    """AC21 (remaining rows): Reject and Withdraw from every active stage, with the note."""

    def test_reject_and_withdraw_from_every_active_stage(self):
        for action, to_stage in EXITS:
            for from_stage in ACTIVE_STAGES:
                with self.subTest(action=action, from_stage=from_stage):
                    self.check_move(action, from_stage, to_stage, note=NOTE)

    def test_the_note_is_recorded_trimmed(self):
        application = make_application(stage=Stage.SCREENING)
        self.move(application, Action.WITHDRAW, note="  Took another offer.\n")
        self.assertEqual(application.stage_changes.last().note, "Took another offer.")

    def test_an_archived_candidate_can_still_be_rejected(self):
        # The archived-candidate guard is for Reactivate only.
        application = make_application(stage=Stage.INTERVIEW)
        Candidate.objects.filter(pk=application.candidate_id).update(archived_at=timezone.now())
        self.move(application, Action.REJECT, note=NOTE)
        self.assertEqual(application.stage, Stage.REJECTED)


class ReactivateTests(TransitionTestCase):
    def exit_then_reactivate(self, application, exit_action, note="Brought back."):
        self.move(application, exit_action, note=NOTE)
        return self.move(application, Action.REACTIVATE, note=note)

    def test_reactivate_from_rejected_and_from_withdrawn(self):
        for exit_action, terminal in EXITS:
            with self.subTest(exit_action=exit_action):
                application = make_application(stage=Stage.INTERVIEW)
                entry = self.exit_then_reactivate(application, exit_action, note=" Misclick. ")
                self.assertEqual(application.stage, Stage.INTERVIEW)
                self.assertEqual((entry.from_stage, entry.to_stage), (terminal, Stage.INTERVIEW))
                self.assertEqual(entry.note, "Misclick.")
                self.assertEqual(entry.changed_by, self.user)
                self.assertEqual(entry, application.stage_changes.last())
                self.assertEqual(application.stage_changed_at, entry.changed_at)
                self.assertEqual(application.stage_changes.count(), 3)

    def test_repeated_cycles_return_to_the_most_recent_active_stage(self):
        # AC24
        application = make_application(stage=Stage.INTERVIEW)
        self.exit_then_reactivate(application, Action.REJECT)
        self.assertEqual(application.stage, Stage.INTERVIEW)
        self.move(application, Action.ADVANCE)
        self.exit_then_reactivate(application, Action.WITHDRAW)
        self.assertEqual(application.stage, Stage.FINAL_REVIEW)
        self.move(application, Action.BACK)
        self.move(application, Action.BACK)
        self.exit_then_reactivate(application, Action.REJECT)
        self.assertEqual(application.stage, Stage.SCREENING)
        self.assertEqual(application.stage_changes.count(), 10)

    def test_the_target_is_read_from_the_history(self):
        application = make_application(stage=Stage.OFFER)
        self.assertIsNone(reactivation_target(application))
        self.move(application, Action.WITHDRAW, note=NOTE)
        self.assertEqual(reactivation_target(application), Stage.OFFER)

    def test_without_an_exit_entry_in_the_history_it_is_refused(self):
        # Only test setup can reach Rejected this way; the service refuses rather than guess.
        self.assert_refused(
            make_application(stage=Stage.REJECTED),
            Action.REACTIVATE,
            "doesn't show which stage to return to",
            note=NOTE,
        )

    def test_an_archived_candidate_blocks_reactivation(self):
        # AC25
        application = make_application(stage=Stage.SCREENING)
        self.move(application, Action.REJECT, note=NOTE)
        Candidate.objects.filter(pk=application.candidate_id).update(archived_at=timezone.now())
        self.assert_refused(
            application, Action.REACTIVATE, "This candidate is archived", note="Back again."
        )

    def test_the_note_check_comes_before_the_archived_guard(self):
        application = make_application(stage=Stage.SCREENING)
        self.move(application, Action.REJECT, note=NOTE)
        Candidate.objects.filter(pk=application.candidate_id).update(archived_at=timezone.now())
        self.assert_refused(application, Action.REACTIVATE, "A note is required to reactivate.")

    def test_a_closed_job_does_not_block_reactivation_and_stays_closed(self):
        # AC25: reactivating isn't new intake, so the job's status is left alone.
        application = make_application(stage=Stage.OFFER)
        self.move(application, Action.REJECT, note=NOTE)
        JobOpening.objects.filter(pk=application.job_opening_id).update(status=JobStatus.CLOSED)
        self.move(application, Action.REACTIVATE, note="Rejected by mistake.")
        self.assertEqual(application.stage, Stage.OFFER)
        self.assertEqual(JobOpening.objects.get().status, JobStatus.CLOSED)


class RequiredNoteTests(TransitionTestCase):
    """AC23: Reject, Withdraw and Reactivate need a note that isn't blank after trimming."""

    BLANK_NOTES = ("", "   ", "\n\t ")

    def test_reject_and_withdraw_without_a_note(self):
        for action, _ in EXITS:
            for note in self.BLANK_NOTES:
                with self.subTest(action=action, note=note):
                    self.assert_refused(
                        make_application(stage=Stage.SCREENING),
                        action,
                        f"A note is required to {action.label.lower()}.",
                        note=note,
                    )

    def test_reactivate_without_a_note(self):
        application = make_application(stage=Stage.SCREENING)
        self.move(application, Action.REJECT, note=NOTE)
        for note in self.BLANK_NOTES:
            with self.subTest(note=note):
                self.assert_refused(
                    application, Action.REACTIVATE, "A note is required to reactivate.", note=note
                )

    def test_a_missing_note_is_refused_as_note_required(self):
        with self.assertRaises(NoteRequired):
            self.move(make_application(), Action.REJECT)

    def test_advance_and_back_need_no_note(self):
        application = make_application(stage=Stage.SCREENING)
        self.move(application, Action.ADVANCE, note="   ")
        self.move(application, Action.BACK)
        self.assertEqual(application.stage, Stage.SCREENING)
        self.assertEqual([c.note for c in application.stage_changes.all()], ["", "", ""])


class HiringHasNoSideEffectsTests(TransitionTestCase):
    """AC26: hiring changes only the selected application."""

    def test_hiring_leaves_other_applications_and_the_job_alone(self):
        application = make_application(stage=Stage.OFFER)
        same_job = make_application(job=application.job_opening, stage=Stage.OFFER)
        same_candidate = make_application(
            candidate=application.candidate, job=make_job("Data Engineer"), stage=Stage.INTERVIEW
        )
        self.move(application, Action.ADVANCE)
        self.assertEqual(application.stage, Stage.HIRED)
        for other, stage in ((same_job, Stage.OFFER), (same_candidate, Stage.INTERVIEW)):
            other.refresh_from_db()
            self.assertEqual(other.stage, stage)
            self.assertEqual(other.stage_changes.count(), 1)
        job = JobOpening.objects.get(pk=application.job_opening_id)
        self.assertEqual(job.status, JobStatus.OPEN)
        self.assertIsNone(Candidate.objects.get(pk=application.candidate_id).archived_at)
        self.assertEqual(StageChange.objects.count(), 4)


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

    def test_a_stale_request_without_a_note_reports_already_updated(self):
        application = make_application(stage=Stage.INTERVIEW)
        self.assert_refused(
            application, Action.REJECT, "already updated", expected_stage=Stage.SCREENING
        )

    def test_a_double_clicked_reject_moves_exactly_once(self):
        application = make_application(stage=Stage.INTERVIEW)
        self.move(application, Action.REJECT, expected_stage=Stage.INTERVIEW, note=NOTE)
        self.assert_refused(
            application,
            Action.REJECT,
            "already updated",
            expected_stage=Stage.INTERVIEW,
            note=NOTE,
        )
        self.assertEqual(application.stage_changes.count(), 2)

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
    """The card renders exactly these (AC29)."""

    def test_moves_for_each_of_the_eight_stages(self):
        exits = [(Action.REJECT, Stage.REJECTED), (Action.WITHDRAW, Stage.WITHDRAWN)]
        expected = {
            Stage.APPLIED: [(Action.ADVANCE, Stage.SCREENING), *exits],
            Stage.SCREENING: [
                (Action.ADVANCE, Stage.INTERVIEW),
                (Action.BACK, Stage.APPLIED),
                *exits,
            ],
            Stage.INTERVIEW: [
                (Action.ADVANCE, Stage.FINAL_REVIEW),
                (Action.BACK, Stage.SCREENING),
                *exits,
            ],
            Stage.FINAL_REVIEW: [
                (Action.ADVANCE, Stage.OFFER),
                (Action.BACK, Stage.INTERVIEW),
                *exits,
            ],
            Stage.OFFER: [(Action.ADVANCE, Stage.HIRED), (Action.BACK, Stage.FINAL_REVIEW), *exits],
            Stage.HIRED: [],
            Stage.REJECTED: [(Action.REACTIVATE, None)],
            Stage.WITHDRAWN: [(Action.REACTIVATE, None)],
        }
        for stage, moves in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual([(m.action, m.target) for m in available_moves(stage)], moves)

    def test_reactivate_carries_the_target_when_known(self):
        self.assertEqual(
            available_moves(Stage.REJECTED, reactivate_to=Stage.INTERVIEW),
            [Move(Action.REACTIVATE, Stage.INTERVIEW)],
        )

    def test_accepts_the_plain_string_stored_in_the_database(self):
        self.assertEqual(len(available_moves("screening")), 4)

    def test_labels_and_which_moves_need_a_note(self):
        cases = [
            (Move(Action.ADVANCE, Stage.HIRED), "Advance to Hired", False),
            (Move(Action.BACK, Stage.APPLIED), "Back to Applied", False),
            (Move(Action.REJECT, Stage.REJECTED), "Reject", True),
            (Move(Action.WITHDRAW, Stage.WITHDRAWN), "Withdraw", True),
            (Move(Action.REACTIVATE, Stage.INTERVIEW), "Reactivate to Interview", True),
            (Move(Action.REACTIVATE, None), "Reactivate", True),
        ]
        for move, label, needs_note in cases:
            with self.subTest(move=move):
                self.assertEqual((move.label, move.needs_note), (label, needs_note))
