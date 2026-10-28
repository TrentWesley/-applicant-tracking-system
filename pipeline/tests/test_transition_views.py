import re

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from core.tests.utils import PASSWORD, make_admin, make_recruiter, make_user
from jobs.models import JobOpening, JobStatus
from pipeline.models import Application, Stage, StageChange
from pipeline.services import Action, change_stage
from pipeline.tests.utils import make_application

HTMX = {"HTTP_HX_REQUEST": "true"}


def transition_url(application):
    return reverse("pipeline:application_transition", args=[application.pk])


def posted_actions(html):
    """The action values of the move forms rendered on a page, in order."""
    return re.findall(r'<input type="hidden" name="action" value="([a-z_]+)">', html)


def confirm_links(html):
    """The actions offered as links that open the inline note form, in order."""
    return re.findall(r'href="[^"]*\?confirm=([a-z]+)"', html)


def has_note_form(html):
    return '<textarea name="note"' in html


def autofocused_links(html):
    """The actions whose note-form links carry autofocus."""
    return re.findall(r'<a href="[^"]*\?confirm=([a-z]+)"[^>]* autofocus[ >]', html)


def note_field_tag(html):
    start = html.index('<textarea name="note"')
    return html[start : html.index(">", start)]


def exit_through_service(application, action=Action.REJECT, note="Not a fit."):
    """Reject or withdraw through the service, so the history knows where to return to."""
    change_stage(
        application=application,
        action=action,
        expected_stage=application.stage,
        changed_by=application.created_by,
        note=note,
    )


class TransitionViewTestCase(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter()
        self.client.force_login(self.recruiter)
        self.application = make_application()

    def post(self, action="advance", expected_stage=None, htmx=True, follow=False, **extra):
        data = {
            "action": action,
            "expected_stage": expected_stage or self.application.stage,
        } | extra
        headers = HTMX if htmx else {}
        return self.client.post(transition_url(self.application), data, follow=follow, **headers)

    def assert_unchanged(self, stage=Stage.APPLIED, changes=1):
        self.application.refresh_from_db()
        self.assertEqual(self.application.stage, stage)
        self.assertEqual(self.application.stage_changes.count(), changes)


class HtmxTransitionTests(TransitionViewTestCase):
    def test_advance_returns_the_refreshed_card_as_a_partial(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/_stage_card.html")
        self.assertTemplateNotUsed(response, "base.html")
        html = response.content.decode()
        self.assertNotIn("<html", html)
        self.assertNotIn('id="nav-drawer"', html)
        self.assertIn('id="stage-card"', html)
        self.assertIn(">Screening</span>", html)
        self.assertIn("Moved from Applied to Screening.", html)
        self.assertIn('role="status"', html)
        self.assert_unchanged(Stage.SCREENING, changes=2)

    def test_the_history_table_is_refreshed_out_of_band(self):
        response = self.post(note="Phone screen booked.")
        html = response.content.decode()
        self.assertIn('id="stage-history"', html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn("Phone screen booked.", html)
        self.assertEqual(self.application.stage_changes.last().note, "Phone screen booked.")

    def test_back_moves_one_stage_back(self):
        self.application = make_application(stage=Stage.INTERVIEW)
        response = self.post("back")
        self.assertContains(response, "Moved from Interview to Screening.")
        self.assert_unchanged(Stage.SCREENING, changes=2)

    def test_a_refused_move_returns_the_card_with_the_reason_and_writes_nothing(self):
        response = self.post("back")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/_stage_card.html")
        self.assertContains(response, "Back isn&#x27;t allowed from Applied.")
        self.assertContains(response, 'role="alert"')
        self.assert_unchanged()

    def test_a_stale_click_returns_the_current_card_and_already_updated(self):
        # AC27: another screen moved it to Screening; this one still shows Applied.
        Application.objects.filter(pk=self.application.pk).update(stage=Stage.SCREENING)
        response = self.post(expected_stage=Stage.APPLIED)
        self.assertContains(response, "This application was already updated")
        self.assertContains(response, ">Screening</span>")
        self.assertContains(response, 'name="expected_stage" value="screening"')
        self.assert_unchanged(Stage.SCREENING, changes=1)

    def test_a_double_click_moves_exactly_once(self):
        # AC28: both requests carry the expected stage the card showed.
        first = self.post(expected_stage=Stage.APPLIED)
        second = self.post(expected_stage=Stage.APPLIED)
        self.assertContains(first, "Moved from Applied to Screening.")
        self.assertContains(second, "already updated")
        self.assert_unchanged(Stage.SCREENING, changes=2)

    def test_a_posted_target_stage_is_ignored(self):
        self.post(stage=Stage.HIRED, to_stage=Stage.HIRED)
        self.assert_unchanged(Stage.SCREENING, changes=2)

    def test_unknown_or_missing_action_is_refused(self):
        for action in ("hire", ""):
            with self.subTest(action=action):
                response = self.post(action)
                self.assertContains(response, "That stage action isn&#x27;t recognised.")
        self.assert_unchanged()

    def test_hired_is_permanent(self):
        self.application = make_application(stage=Stage.HIRED)
        response = self.post()
        self.assertContains(response, "Hired is permanent")
        self.assert_unchanged(Stage.HIRED)

    def test_moving_to_hired_from_offer(self):
        self.application = make_application(stage=Stage.OFFER)
        self.assertContains(self.post(), "Moved from Offer to Hired.")
        self.assert_unchanged(Stage.HIRED, changes=2)


class PlainPostTransitionTests(TransitionViewTestCase):
    """Without HTMX the same forms still work: the move happens and the detail page reloads."""

    def test_success_redirects_to_the_detail_page_with_a_message(self):
        response = self.post(htmx=False, follow=True)
        self.assertRedirects(response, self.application.get_absolute_url())
        self.assertContains(response, "Moved from Applied to Screening.")
        self.assert_unchanged(Stage.SCREENING, changes=2)

    def test_refusal_redirects_with_the_reason(self):
        response = self.post("back", htmx=False, follow=True)
        self.assertRedirects(response, self.application.get_absolute_url())
        self.assertContains(response, "Back isn&#x27;t allowed from Applied.")
        self.assertContains(response, "alert-error")
        self.assert_unchanged()

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(transition_url(self.application)).status_code, 405)
        self.assert_unchanged()

    def test_unknown_application_is_404(self):
        response = self.client.post("/applications/999999/transition/", {"action": "advance"})
        self.assertEqual(response.status_code, 404)


class TransitionPermissionTests(TransitionViewTestCase):
    def test_recruiter_and_admin_can_move_applications(self):
        for user in (make_recruiter("rita"), make_admin()):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.application = make_application()
                self.assertContains(self.post(), "Moved from Applied to Screening.")
                self.assertEqual(self.application.stage_changes.last().changed_by, user)

    def test_user_without_change_permission_gets_403_and_nothing_changes(self):
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_application"))
        for user in (viewer, make_user("nobody")):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.post().status_code, 403)
                self.assert_unchanged()

    def test_anonymous_post_is_redirected_to_login_and_nothing_changes(self):
        self.client.logout()
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assert_unchanged()


class TransitionCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        make_recruiter("rita")
        self.client.login(username="rita", password=PASSWORD)
        self.application = make_application()
        self.data = {"action": "advance", "expected_stage": Stage.APPLIED}

    def test_a_post_without_a_csrf_token_is_refused(self):
        response = self.client.post(transition_url(self.application), self.data, **HTMX)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Application.objects.get().stage, Stage.APPLIED)
        self.assertEqual(StageChange.objects.count(), 1)

    def test_htmx_sends_the_token_from_the_page_header(self):
        page = self.client.get(self.application.get_absolute_url())
        token = str(page.context["csrf_token"])
        response = self.client.post(
            transition_url(self.application), self.data, HTTP_X_CSRFTOKEN=token, **HTMX
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.get().stage, Stage.SCREENING)


class StageCardRenderingTests(TestCase):
    """AC29: the card renders exactly the moves allowed for each stage."""

    # (single-click forms, links that open a note form)
    EXPECTED = {
        Stage.APPLIED: (["advance"], ["reject", "withdraw"]),
        Stage.SCREENING: (["advance", "back"], ["reject", "withdraw"]),
        Stage.INTERVIEW: (["advance", "back"], ["reject", "withdraw"]),
        Stage.FINAL_REVIEW: (["advance", "back"], ["reject", "withdraw"]),
        Stage.OFFER: (["advance", "back"], ["reject", "withdraw"]),
        Stage.HIRED: ([], []),
        Stage.REJECTED: ([], ["reactivate"]),
        Stage.WITHDRAWN: ([], ["reactivate"]),
    }

    def setUp(self):
        self.client.force_login(make_recruiter())

    def test_buttons_for_each_of_the_eight_stages(self):
        for stage, (forms, links) in self.EXPECTED.items():
            with self.subTest(stage=stage):
                application = make_application(stage=stage)
                response = self.client.get(application.get_absolute_url())
                html = response.content.decode()
                self.assertIn('id="stage-card"', html)
                self.assertEqual(posted_actions(html), forms)
                self.assertEqual(confirm_links(html), links)
                self.assertFalse(has_note_form(html))
                self.assertEqual(
                    html.count(f'name="expected_stage" value="{stage.value}"'), len(forms)
                )

    def test_reactivate_names_the_stage_it_returns_to(self):
        application = make_application(stage=Stage.INTERVIEW)
        exit_through_service(application, Action.WITHDRAW)
        response = self.client.get(application.get_absolute_url())
        self.assertContains(response, "Reactivate to Interview")

    def test_note_links_open_the_form_with_htmx(self):
        application = make_application(stage=Stage.SCREENING)
        response = self.client.get(application.get_absolute_url())
        url = application.get_absolute_url()
        self.assertContains(response, f'href="{url}?confirm=reject"')
        self.assertContains(response, f'hx-get="{url}?confirm=reject"')
        self.assertContains(response, f'hx-get="{url}?confirm=withdraw"')
        self.assertContains(response, 'hx-target="#stage-card"', count=4)

    def test_buttons_name_the_destination_and_post_with_htmx(self):
        application = make_application(stage=Stage.OFFER)
        response = self.client.get(application.get_absolute_url())
        url = transition_url(application)
        self.assertContains(response, "Advance to Hired")
        self.assertContains(response, "Back to Final Review")
        self.assertContains(response, f'action="{url}"', count=2)
        self.assertContains(response, f'hx-post="{url}"', count=2)
        self.assertContains(response, 'hx-target="#stage-card"', count=4)  # + Reject, Withdraw
        self.assertContains(response, 'hx-disabled-elt="find button"', count=2)

    def test_hired_card_explains_it_is_permanent(self):
        application = make_application(stage=Stage.HIRED)
        response = self.client.get(application.get_absolute_url())
        self.assertContains(response, "Hired is permanent.")

    def test_view_only_users_see_no_move_buttons(self):
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_application"))
        self.client.force_login(viewer)
        application = make_application(stage=Stage.SCREENING)
        response = self.client.get(application.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(posted_actions(html), [])
        self.assertEqual(confirm_links(html), [])
        # Opening the note form by URL doesn't show it either.
        response = self.client.get(f"{application.get_absolute_url()}?confirm=reject")
        self.assertFalse(has_note_form(response.content.decode()))


class NoteFormTests(TestCase):
    """The inline note form: an HTMX GET swaps it into the card; Cancel restores the card."""

    def setUp(self):
        self.client.force_login(make_recruiter())
        self.application = make_application(stage=Stage.INTERVIEW)

    def get(self, confirm=None, htmx=True, focus=None):
        url = self.application.get_absolute_url()
        if confirm is not None:
            url = f"{url}?confirm={confirm}"
        if focus is not None:
            url = f"{url}?focus={focus}"
        return self.client.get(url, **(HTMX if htmx else {}))

    def test_htmx_get_returns_the_card_with_the_note_form_as_a_partial(self):
        response = self.get("reject")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/_stage_card.html")
        self.assertTemplateNotUsed(response, "base.html")
        html = response.content.decode()
        self.assertNotIn("<html", html)
        self.assertIn('id="stage-card"', html)
        self.assertTrue(has_note_form(html))
        self.assertIn(" required", note_field_tag(html))
        self.assertIn(" autofocus", note_field_tag(html))
        self.assertEqual(posted_actions(html), ["reject"])
        self.assertIn('name="expected_stage" value="interview"', html)
        url = transition_url(self.application)
        self.assertIn(f'hx-post="{url}"', html)
        self.assertIn(f'action="{url}"', html)
        self.assertIn('hx-disabled-elt="find button"', html)
        self.assertIn(">Confirm</button>", html)
        cancel = f"{self.application.get_absolute_url()}?focus=reject"
        self.assertIn(f'href="{cancel}" hx-get="{cancel}"', html)
        self.assertIn(">Cancel</a>", html)

    def test_each_note_action_has_its_own_form(self):
        for action, heading in (("reject", "Reject"), ("withdraw", "Withdraw")):
            with self.subTest(action=action):
                html = self.get(action).content.decode()
                self.assertEqual(posted_actions(html), [action])
                self.assertIn(f"{heading} this application", html)

    def test_the_reactivate_form_says_where_it_returns(self):
        exit_through_service(self.application)
        html = self.get("reactivate").content.decode()
        self.assertEqual(posted_actions(html), ["reactivate"])
        self.assertIn('name="expected_stage" value="rejected"', html)
        self.assertIn("Returns to Interview.", html)

    def test_cancel_restores_the_card_without_the_form(self):
        response = self.get()
        self.assertTemplateNotUsed(response, "base.html")
        html = response.content.decode()
        self.assertIn('id="stage-card"', html)
        self.assertFalse(has_note_form(html))
        self.assertEqual(confirm_links(html), ["reject", "withdraw"])

    def test_page_and_card_are_cached_separately(self):
        for htmx in (True, False):
            with self.subTest(htmx=htmx):
                self.assertIn("HX-Request", self.get("reject", htmx=htmx)["Vary"])

    def test_without_htmx_the_link_opens_the_full_page_with_the_form(self):
        response = self.get("withdraw", htmx=False)
        self.assertTemplateUsed(response, "base.html")
        self.assertTrue(has_note_form(response.content.decode()))
        self.assertContains(
            response, f'href="{self.application.get_absolute_url()}?focus=withdraw"'
        )

    def test_cancel_returns_focus_to_the_link_that_opened_the_form(self):
        # Regression: after Cancel, keyboard focus fell back to the page body.
        for action in ("reject", "withdraw"):
            for htmx in (True, False):
                with self.subTest(action=action, htmx=htmx):
                    html = self.get(htmx=htmx, focus=action).content.decode()
                    self.assertFalse(has_note_form(html))
                    self.assertEqual(autofocused_links(html), [action])

    def test_cancel_from_reactivate_focuses_reactivate(self):
        exit_through_service(self.application)
        html = self.get(focus="reactivate").content.decode()
        self.assertEqual(autofocused_links(html), ["reactivate"])

    def test_focus_is_ignored_for_actions_without_a_link(self):
        for focus in ("advance", "back", "reactivate", "hire", ""):
            with self.subTest(focus=focus):
                self.assertEqual(autofocused_links(self.get(focus=focus).content.decode()), [])

    def test_no_form_for_an_action_the_stage_does_not_allow(self):
        for confirm in ("reactivate", "advance", "back", "hire", ""):
            with self.subTest(confirm=confirm):
                self.assertFalse(has_note_form(self.get(confirm).content.decode()))

    def test_no_form_on_hired(self):
        self.application = make_application(stage=Stage.HIRED)
        for confirm in ("reject", "withdraw", "reactivate"):
            with self.subTest(confirm=confirm):
                html = self.get(confirm).content.decode()
                self.assertFalse(has_note_form(html))
                self.assertEqual(posted_actions(html), [])


class NoteMoveTransitionTests(TransitionViewTestCase):
    """Reject, Withdraw and Reactivate post the note to the same transition endpoint."""

    def setUp(self):
        super().setUp()
        self.application = make_application(stage=Stage.INTERVIEW)

    def test_reject_with_a_note(self):
        response = self.post("reject", note="Not enough SQL experience.")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, "base.html")
        html = response.content.decode()
        self.assertIn("Moved from Interview to Rejected.", html)
        self.assertIn('role="status"', html)
        self.assertFalse(has_note_form(html))
        self.assertEqual(confirm_links(html), ["reactivate"])
        self.assertIn("Reactivate to Interview", html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn("Not enough SQL experience.", html)  # in the refreshed history
        self.assert_unchanged(Stage.REJECTED, changes=2)
        entry = self.application.stage_changes.last()
        self.assertEqual(entry.note, "Not enough SQL experience.")
        self.assertEqual(entry.changed_by, self.recruiter)

    def test_withdraw_with_a_note(self):
        self.assertContains(self.post("withdraw", note="Took another offer."), "to Withdrawn.")
        self.assert_unchanged(Stage.WITHDRAWN, changes=2)

    def test_a_blank_note_is_refused_and_the_form_stays_open(self):
        for note in ("", "   "):
            with self.subTest(note=note):
                response = self.post("reject", note=note)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("A note is required to reject.", html)
                self.assertIn('role="alert"', html)
                self.assertTrue(has_note_form(html))
                self.assertIn('aria-invalid="true"', note_field_tag(html))
                self.assertEqual(posted_actions(html), ["reject"])
        self.assert_unchanged(Stage.INTERVIEW, changes=1)

    def test_a_stale_reject_without_a_note_says_already_updated_and_closes_the_form(self):
        Application.objects.filter(pk=self.application.pk).update(stage=Stage.OFFER)
        response = self.post("reject", expected_stage=Stage.INTERVIEW)
        html = response.content.decode()
        self.assertIn("already updated", html)
        self.assertNotIn("A note is required", html)
        self.assertFalse(has_note_form(html))
        self.assert_unchanged(Stage.OFFER, changes=1)

    def test_a_double_clicked_confirm_moves_exactly_once(self):
        first = self.post("withdraw", expected_stage=Stage.INTERVIEW, note="Moved city.")
        second = self.post("withdraw", expected_stage=Stage.INTERVIEW, note="Moved city.")
        self.assertContains(first, "Moved from Interview to Withdrawn.")
        self.assertContains(second, "already updated")
        self.assert_unchanged(Stage.WITHDRAWN, changes=2)

    def test_reactivate_returns_to_the_stage_it_left(self):
        exit_through_service(self.application)
        response = self.post("reactivate", note="Rejected by mistake.")
        self.assertContains(response, "Moved from Rejected to Interview.")
        self.assert_unchanged(Stage.INTERVIEW, changes=3)

    def test_reactivate_is_refused_for_an_archived_candidate(self):
        exit_through_service(self.application)
        Candidate.objects.filter(pk=self.application.candidate_id).update(
            archived_at=timezone.now()
        )
        response = self.post("reactivate", note="Back again.")
        html = response.content.decode()
        self.assertIn("This candidate is archived", html)
        self.assertIn('role="alert"', html)
        self.assertFalse(has_note_form(html))
        self.assert_unchanged(Stage.REJECTED, changes=2)

    def test_reactivate_works_on_a_closed_job_and_leaves_it_closed(self):
        exit_through_service(self.application)
        JobOpening.objects.filter(pk=self.application.job_opening_id).update(
            status=JobStatus.CLOSED
        )
        self.assertContains(self.post("reactivate", note="Misclick."), "to Interview.")
        self.assert_unchanged(Stage.INTERVIEW, changes=3)
        job = JobOpening.objects.get(pk=self.application.job_opening_id)
        self.assertEqual(job.status, JobStatus.CLOSED)

    def test_hired_refuses_every_note_action(self):
        self.application = make_application(stage=Stage.HIRED)
        for action in ("reject", "withdraw", "reactivate"):
            with self.subTest(action=action):
                response = self.post(action, note="Changed our minds.")
                self.assertContains(response, "Hired is permanent")
                self.assertFalse(has_note_form(response.content.decode()))
        self.assert_unchanged(Stage.HIRED)

    def test_plain_post_with_a_blank_note_reopens_the_form_with_the_reason(self):
        response = self.post("reject", htmx=False, follow=True)
        self.assertRedirects(response, f"{self.application.get_absolute_url()}?confirm=reject")
        self.assertContains(response, "A note is required to reject.")
        self.assertTrue(has_note_form(response.content.decode()))
        self.assert_unchanged(Stage.INTERVIEW)

    def test_plain_post_with_a_note_redirects_to_the_detail_page(self):
        response = self.post("withdraw", htmx=False, follow=True, note="Moved city.")
        self.assertRedirects(response, self.application.get_absolute_url())
        self.assertContains(response, "Moved from Interview to Withdrawn.")

    def test_users_without_change_permission_get_403(self):
        viewer = make_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_application"))
        self.client.force_login(viewer)
        self.assertEqual(self.post("reject", note="No.").status_code, 403)
        self.assert_unchanged(Stage.INTERVIEW)
