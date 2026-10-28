"""Phase 9: editing an application's general notes (US 49, AC34)."""

from unittest import mock

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import Application, Stage, StageChange
from pipeline.services import change_stage
from pipeline.tests.utils import make_application

HTMX = {"HTTP_HX_REQUEST": "true"}


def notes_url(application):
    return reverse("pipeline:application_notes", args=[application.pk])


def move(application, action, note=""):
    change_stage(
        application=application,
        action=action,
        expected_stage=application.stage,
        changed_by=application.created_by,
        note=note,
    )


class NotesTestCase(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter()
        self.client.force_login(self.recruiter)
        self.application = make_application(notes="Referred by Sam.")
        move(self.application, "advance", "Phone screen booked.")

    def post(self, notes, htmx=True, follow=False, **extra):
        headers = HTMX if htmx else {}
        return self.client.post(
            notes_url(self.application), {"notes": notes} | extra, follow=follow, **headers
        )

    def snapshot(self):
        """Everything a notes edit must leave alone."""
        a = Application.objects.get(pk=self.application.pk)
        history = list(
            StageChange.objects.filter(application=a).values_list(
                "pk", "from_stage", "to_stage", "changed_by", "changed_at", "note"
            )
        )
        return (
            a.stage,
            a.stage_changed_at,
            a.candidate_id,
            a.job_opening_id,
            a.created_by_id,
            a.created_at,
            history,
        )

    def stored_notes(self):
        return Application.objects.get(pk=self.application.pk).notes


class EditNotesTests(NotesTestCase):
    def test_htmx_edit_returns_the_notes_partial_and_changes_only_notes(self):
        # AC34
        before = self.snapshot()
        response = self.post("Strong SQL; prefers hybrid.")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/_notes_card.html")
        self.assertTemplateNotUsed(response, "base.html")
        html = response.content.decode()
        self.assertNotIn("<html", html)
        self.assertIn('id="notes-card"', html)
        self.assertIn("Notes saved.", html)
        self.assertIn('role="status"', html)
        self.assertIn("Strong SQL; prefers hybrid.</textarea>", html)
        self.assertEqual(self.stored_notes(), "Strong SQL; prefers hybrid.")
        self.assertEqual(self.snapshot(), before)

    def test_notes_can_be_cleared(self):
        before = self.snapshot()
        self.post("")
        self.assertEqual(self.stored_notes(), "")
        self.assertEqual(self.snapshot(), before)

    def test_other_posted_fields_are_ignored(self):
        before = self.snapshot()
        self.post(
            "Updated.",
            stage=Stage.HIRED,
            stage_changed_at="2020-01-01 00:00",
            candidate=make_candidate("other@example.com").pk,
            job_opening=make_job("Other").pk,
            created_by=make_admin().pk,
        )
        self.assertEqual(self.stored_notes(), "Updated.")
        self.assertEqual(self.snapshot(), before)

    def test_without_htmx_it_redirects_to_the_detail_page_with_a_message(self):
        response = self.post("Plain form post.", htmx=False, follow=True)
        self.assertRedirects(response, self.application.get_absolute_url())
        self.assertContains(response, "Notes saved.")
        self.assertContains(response, "Plain form post.</textarea>")
        self.assertEqual(self.stored_notes(), "Plain form post.")

    def test_notes_stay_editable_whatever_the_stage_job_or_candidate(self):
        # Hired is permanent for the stage only; closed jobs and archived candidates keep
        # their records, and a notes save never touches the stage (or its database guard).
        move(self.application, "reject", "Not this time.")
        JobOpening.objects.filter(pk=self.application.job_opening_id).update(
            status=JobStatus.CLOSED
        )
        Candidate.objects.filter(pk=self.application.candidate_id).update(
            archived_at=timezone.now()
        )
        before = self.snapshot()
        self.post("Kept on file for next year.")
        self.assertEqual(self.stored_notes(), "Kept on file for next year.")
        self.assertEqual(self.snapshot(), before)
        hired = make_application(stage=Stage.HIRED)
        self.client.post(notes_url(hired), {"notes": "Starts Monday."}, **HTMX)
        self.assertEqual(Application.objects.get(pk=hired.pk).notes, "Starts Monday.")

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(notes_url(self.application)).status_code, 405)

    def test_unknown_application_is_404(self):
        self.assertEqual(self.client.post("/applications/999999/notes/").status_code, 404)


class StaleNotesFormTests(NotesTestCase):
    """
    Regression: a notes edit whose request loaded the application before another request moved
    it must not write the old stage back (or trip the archived-candidate guard).
    """

    def post_with_application_loaded_before(self, other_request, notes="Edited."):
        stale = Application.objects.get(pk=self.application.pk)  # the notes request's copy
        other_request()
        with mock.patch("pipeline.views.ApplicationNotesView.get_object", return_value=stale):
            return self.post(notes)

    def test_a_stage_move_during_a_notes_edit_is_kept(self):
        def advance():
            move(Application.objects.get(pk=self.application.pk), "advance")

        response = self.post_with_application_loaded_before(advance)
        self.assertEqual(response.status_code, 200)
        stored = Application.objects.get(pk=self.application.pk)
        self.assertEqual(stored.stage, Stage.INTERVIEW)
        self.assertEqual(stored.stage_changed_at, stored.stage_changes.last().changed_at)
        self.assertEqual(stored.stage_changes.count(), 3)
        self.assertEqual(stored.notes, "Edited.")

    def test_a_reject_and_archive_during_a_notes_edit(self):
        # A full save would write back Screening for an archived candidate, which the database
        # guard refuses; the targeted update never touches the stage.
        def reject_and_archive():
            move(Application.objects.get(pk=self.application.pk), "reject", "No.")
            Candidate.objects.filter(pk=self.application.candidate_id).update(
                archived_at=timezone.now()
            )

        response = self.post_with_application_loaded_before(reject_and_archive)
        self.assertEqual(response.status_code, 200)
        stored = Application.objects.get(pk=self.application.pk)
        self.assertEqual(stored.stage, Stage.REJECTED)
        self.assertEqual(stored.notes, "Edited.")


class NotesPermissionTests(NotesTestCase):
    def test_recruiter_and_admin_can_edit_notes(self):
        for user in (make_recruiter("rita"), make_admin()):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.post(f"Edited by {user.username}.")
                self.assertEqual(self.stored_notes(), f"Edited by {user.username}.")

    def test_view_only_user_gets_403_and_sees_read_only_notes(self):
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_application"))
        self.client.force_login(viewer)
        self.assertEqual(self.post("Sneaky.").status_code, 403)
        self.assertEqual(self.stored_notes(), "Referred by Sam.")
        response = self.client.get(self.application.get_absolute_url())
        self.assertContains(response, "Referred by Sam.")
        self.assertNotContains(response, notes_url(self.application))
        self.assertNotContains(response, '<textarea name="notes"')

    def test_anonymous_post_is_redirected_to_login(self):
        self.client.logout()
        response = self.post("Sneaky.")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(self.stored_notes(), "Referred by Sam.")


class NotesOnTheDetailPageTests(NotesTestCase):
    def test_the_detail_page_has_a_labelled_notes_form(self):
        response = self.client.get(self.application.get_absolute_url())
        url = notes_url(self.application)
        self.assertContains(response, 'id="notes-card"')
        self.assertContains(response, f'action="{url}"')  # works without JavaScript
        self.assertContains(response, f'hx-post="{url}"')
        self.assertContains(response, 'hx-target="#notes-card"')
        self.assertContains(response, '<label for="id_notes"')
        self.assertContains(response, "Referred by Sam.</textarea>")
        self.assertContains(response, ">Save notes</button>")

    def test_stage_history_and_its_notes_stay_read_only(self):
        # AC34, AC30: the history section has no form or input, and its notes are shown as text.
        html = self.client.get(self.application.get_absolute_url()).content.decode()
        start = html.index('id="stage-history"')
        history = html[start : html.index("</section>", start)]
        self.assertIn("Phone screen booked.", history)
        self.assertNotIn("<form", history)
        self.assertNotIn("<textarea", history)
