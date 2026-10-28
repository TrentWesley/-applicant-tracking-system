from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from candidates.services import CandidateStatusRefused, archive_candidate, restore_candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.tests.utils import make_job
from pipeline.forms import ARCHIVED_CANDIDATE_CHOICE_MESSAGE
from pipeline.models import Application, Stage, StageChange
from pipeline.services import (
    CANDIDATE_ARCHIVED_MESSAGE,
    StageChangeRefused,
    change_stage,
    create_application,
)
from pipeline.tests.utils import make_application

LIST_URL = reverse("candidates:candidate_list")
ARCHIVED_URL = reverse("candidates:candidate_archived_list")


def archive_url(candidate):
    return reverse("candidates:candidate_archive", args=[candidate.pk])


def restore_url(candidate):
    return reverse("candidates:candidate_restore", args=[candidate.pk])


def snapshot(candidate):
    """Every application of the candidate, with its stage, stage time and history size."""
    return [
        (a.pk, a.stage, a.stage_changed_at, a.stage_changes.count())
        for a in Application.objects.filter(candidate=candidate).order_by("pk")
    ]


def exit_application(application, action="reject"):
    change_stage(
        application=application,
        action=action,
        expected_stage=application.stage,
        changed_by=application.created_by,
        note="Not this time.",
    )


class ArchiveServiceTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate()

    def test_a_candidate_with_no_applications_can_be_archived(self):
        before = self.candidate.updated_at
        archive_candidate(self.candidate)
        self.assertIsNotNone(self.candidate.archived_at)  # refreshed in place
        stored = Candidate.objects.get()
        self.assertEqual(stored.archived_at, self.candidate.archived_at)
        self.assertGreater(stored.updated_at, before)

    def test_terminal_applications_allow_archiving_including_hired(self):
        # AC6, US 13
        for stage in (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN):
            make_application(candidate=self.candidate, job=make_job(f"Role {stage}"), stage=stage)
        archive_candidate(self.candidate)
        self.assertIsNotNone(Candidate.objects.get().archived_at)

    def test_any_active_application_refuses_and_lists_them(self):
        # AC6, US 12
        interview = make_application(
            candidate=self.candidate, job=make_job("Data Analyst"), stage=Stage.INTERVIEW
        )
        offer = make_application(
            candidate=self.candidate, job=make_job("Data Engineer"), stage=Stage.OFFER
        )
        make_application(candidate=self.candidate, job=make_job("Clerk"), stage=Stage.HIRED)
        with self.assertRaises(CandidateStatusRefused) as refusal:
            archive_candidate(self.candidate)
        self.assertEqual(
            str(refusal.exception),
            "Ann Lee can't be archived while they have active applications: "
            "Data Analyst (Interview), Data Engineer (Offer). "
            "Move each one to Hired, Rejected or Withdrawn first.",
        )
        self.assertEqual(refusal.exception.applications, [interview, offer])
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_every_active_stage_blocks_archiving(self):
        for stage in (
            Stage.APPLIED,
            Stage.SCREENING,
            Stage.INTERVIEW,
            Stage.FINAL_REVIEW,
            Stage.OFFER,
        ):
            with self.subTest(stage=stage):
                candidate = make_candidate(f"{stage}@example.com")
                make_application(candidate=candidate, stage=stage)
                with self.assertRaises(CandidateStatusRefused):
                    archive_candidate(candidate)
                self.assertIsNone(Candidate.objects.get(pk=candidate.pk).archived_at)

    def test_archiving_twice_is_refused_and_changes_nothing(self):
        archive_candidate(self.candidate)
        archived_at = Candidate.objects.get().archived_at
        with self.assertRaisesMessage(CandidateStatusRefused, "already archived"):
            archive_candidate(self.candidate)
        self.assertEqual(Candidate.objects.get().archived_at, archived_at)

    def test_restore_clears_archived_at(self):
        archive_candidate(self.candidate)
        restore_candidate(self.candidate)
        self.assertIsNone(self.candidate.archived_at)
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_restoring_an_active_candidate_is_refused(self):
        with self.assertRaisesMessage(CandidateStatusRefused, "already active"):
            restore_candidate(self.candidate)

    def test_a_stale_candidate_object_reads_the_database(self):
        Candidate.objects.filter(pk=self.candidate.pk).update(archived_at=timezone.now())
        with self.assertRaisesMessage(CandidateStatusRefused, "already archived"):
            archive_candidate(self.candidate)
        self.assertIsNotNone(self.candidate.archived_at)  # refreshed even when refused

    def test_archive_and_restore_change_no_application_or_history(self):
        # AC8, and no side effects: the Hired application, its history and the job's hired
        # count are unchanged.
        job = make_job("Data Analyst")
        hired = make_application(candidate=self.candidate, job=job)
        for _ in range(5):
            change_stage(
                application=hired,
                action="advance",
                expected_stage=hired.stage,
                changed_by=hired.created_by,
            )
        exit_application(make_application(candidate=self.candidate, stage=Stage.SCREENING))
        before, history = snapshot(self.candidate), StageChange.objects.count()
        archive_candidate(self.candidate)
        self.assertEqual(snapshot(self.candidate), before)
        self.assertEqual(job.applications.filter(stage=Stage.HIRED).count(), 1)
        restore_candidate(self.candidate)
        self.assertEqual(snapshot(self.candidate), before)
        self.assertEqual(StageChange.objects.count(), history)


class ArchivedCandidatesAreBlockedTests(TestCase):
    """AC9 and AC25 (archived part)."""

    def setUp(self):
        self.recruiter = make_recruiter()
        self.candidate = make_candidate()

    def test_no_new_application_through_the_service(self):
        archive_candidate(self.candidate)
        with self.assertRaisesMessage(StageChangeRefused, CANDIDATE_ARCHIVED_MESSAGE):
            create_application(
                candidate=self.candidate, job_opening=make_job(), created_by=self.recruiter
            )
        self.assertFalse(Application.objects.exists())

    def test_no_new_application_through_a_direct_post(self):
        archive_candidate(self.candidate)
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("pipeline:application_create"),
            {"candidate": self.candidate.pk, "job_opening": make_job().pk, "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors["candidate"], [ARCHIVED_CANDIDATE_CHOICE_MESSAGE]
        )
        self.assertFalse(Application.objects.exists())

    def test_the_create_form_does_not_offer_archived_candidates(self):
        archive_candidate(self.candidate)
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("pipeline:application_create"), {"candidate": self.candidate.pk}
        )
        self.assertNotContains(response, f'value="{self.candidate.pk}"')

    def test_reactivation_is_refused_until_restored(self):
        application = make_application(candidate=self.candidate, stage=Stage.INTERVIEW)
        exit_application(application, "withdraw")
        archive_candidate(self.candidate)
        count = StageChange.objects.count()
        with self.assertRaisesMessage(StageChangeRefused, "This candidate is archived"):
            change_stage(
                application=application,
                action="reactivate",
                expected_stage=Stage.WITHDRAWN,
                changed_by=self.recruiter,
                note="Came back.",
            )
        self.assertEqual(StageChange.objects.count(), count)
        restore_candidate(self.candidate)
        change_stage(
            application=application,
            action="reactivate",
            expected_stage=Stage.WITHDRAWN,
            changed_by=self.recruiter,
            note="Came back.",
        )
        self.assertEqual(application.stage, Stage.INTERVIEW)

    def test_after_restore_new_applications_are_allowed(self):
        archive_candidate(self.candidate)
        restore_candidate(self.candidate)
        create_application(
            candidate=self.candidate, job_opening=make_job(), created_by=self.recruiter
        )
        self.assertEqual(Application.objects.count(), 1)


class ArchiveViewTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate()
        self.client.force_login(make_recruiter())

    def test_archive_redirects_to_the_candidate_with_a_message(self):
        response = self.client.post(archive_url(self.candidate), follow=True)
        self.assertRedirects(response, self.candidate.get_absolute_url())
        self.assertContains(response, "Ann Lee archived.")
        self.assertContains(response, "alert-success")
        self.assertIsNotNone(Candidate.objects.get().archived_at)

    def test_refused_archive_shows_the_active_applications(self):
        make_application(candidate=self.candidate, job=make_job("Data Analyst"))
        response = self.client.post(archive_url(self.candidate), follow=True)
        self.assertContains(response, "alert-error")
        self.assertContains(response, "active applications: Data Analyst (Applied).")
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_restore_redirects_with_a_message(self):
        archive_candidate(self.candidate)
        response = self.client.post(restore_url(self.candidate), follow=True)
        self.assertRedirects(response, self.candidate.get_absolute_url())
        self.assertContains(response, "Ann Lee restored.")
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_repeated_archive_and_restore_are_refused_clearly(self):
        self.client.post(archive_url(self.candidate))
        response = self.client.post(archive_url(self.candidate), follow=True)
        self.assertContains(response, "This candidate is already archived, so nothing was changed.")
        self.client.post(restore_url(self.candidate))
        response = self.client.post(restore_url(self.candidate), follow=True)
        self.assertContains(response, "This candidate is already active, so nothing was changed.")
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_get_is_not_allowed(self):
        for url in (archive_url(self.candidate), restore_url(self.candidate)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertIsNone(Candidate.objects.get().archived_at)

    def test_unknown_candidate_is_404(self):
        self.assertEqual(self.client.post("/candidates/999999/archive/").status_code, 404)
        self.assertEqual(self.client.post("/candidates/999999/restore/").status_code, 404)


class ArchivePermissionTests(TestCase):
    def test_recruiter_and_admin_can_archive_and_restore(self):
        # AC2
        for user in (make_recruiter(), make_admin()):
            with self.subTest(user=user.username):
                candidate = make_candidate(f"{user.username}@example.com")
                self.client.force_login(user)
                self.client.post(archive_url(candidate))
                self.assertIsNotNone(Candidate.objects.get(pk=candidate.pk).archived_at)
                self.client.post(restore_url(candidate))
                self.assertIsNone(Candidate.objects.get(pk=candidate.pk).archived_at)

    def test_view_only_user_gets_403_and_nothing_changes(self):
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_candidate"))
        active, archived = make_candidate(), make_candidate("old@example.com")
        archive_candidate(archived)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(archive_url(active)).status_code, 403)
        self.assertEqual(self.client.post(restore_url(archived)).status_code, 403)
        self.assertIsNone(Candidate.objects.get(pk=active.pk).archived_at)
        self.assertIsNotNone(Candidate.objects.get(pk=archived.pk).archived_at)
        for candidate in (active, archived):
            html = self.client.get(candidate.get_absolute_url()).content.decode()
            self.assertNotIn(archive_url(candidate), html)
            self.assertNotIn(restore_url(candidate), html)

    def test_anonymous_post_is_redirected_to_login(self):
        candidate = make_candidate()
        response = self.client.post(archive_url(candidate))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertIsNone(Candidate.objects.get().archived_at)


class ArchivedListAndDetailTests(TestCase):
    """AC7, US 14."""

    def setUp(self):
        self.client.force_login(make_recruiter())
        self.active = make_candidate("active@example.com", first_name="Ada")
        self.archived = make_candidate("gone@example.com", first_name="Gus")
        archive_candidate(self.archived)

    def test_default_list_excludes_archived_and_links_to_the_archived_view(self):
        response = self.client.get(LIST_URL)
        self.assertContains(response, "Ada Lee")
        self.assertNotContains(response, "Gus Lee")
        self.assertContains(response, f'href="{ARCHIVED_URL}"')

    def test_archived_view_lists_only_archived_candidates(self):
        response = self.client.get(ARCHIVED_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Archived candidates</h1>")
        self.assertContains(response, "Gus Lee")
        self.assertNotContains(response, "Ada Lee")
        self.assertContains(response, f'href="{LIST_URL}"')
        self.assertContains(response, 'aria-current="page"')  # Candidates nav stays highlighted

    def test_archived_view_needs_view_permission(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(self.client.get(ARCHIVED_URL).status_code, 403)

    def test_active_detail_offers_archive_and_new_application(self):
        response = self.client.get(self.active.get_absolute_url())
        self.assertContains(response, f'<form method="post" action="{archive_url(self.active)}"')
        self.assertContains(response, ">Archive candidate</button>")
        self.assertNotContains(response, restore_url(self.active))
        self.assertContains(response, "New application")

    def test_archived_detail_offers_restore_and_no_new_application(self):
        response = self.client.get(self.archived.get_absolute_url())
        self.assertContains(response, f'<form method="post" action="{restore_url(self.archived)}"')
        self.assertContains(response, ">Restore candidate</button>")
        self.assertNotContains(response, archive_url(self.archived))
        self.assertNotContains(response, "New application")
        self.assertContains(response, ">Archived<")
        self.assertContains(response, f'href="{ARCHIVED_URL}"')  # back to the archived list
