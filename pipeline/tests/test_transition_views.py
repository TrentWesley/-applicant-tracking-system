import re

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from core.tests.utils import PASSWORD, make_admin, make_recruiter, make_user
from pipeline.models import Application, Stage, StageChange
from pipeline.tests.utils import make_application

HTMX = {"HTTP_HX_REQUEST": "true"}


def transition_url(application):
    return reverse("pipeline:application_transition", args=[application.pk])


def posted_actions(html):
    """The action values of the move forms rendered on a page, in order."""
    return re.findall(r'<input type="hidden" name="action" value="([a-z_]+)">', html)


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

    EXPECTED = {
        Stage.APPLIED: ["advance"],
        Stage.SCREENING: ["advance", "back"],
        Stage.INTERVIEW: ["advance", "back"],
        Stage.FINAL_REVIEW: ["advance", "back"],
        Stage.OFFER: ["advance", "back"],
        Stage.HIRED: [],
        Stage.REJECTED: [],
        Stage.WITHDRAWN: [],
    }

    def setUp(self):
        self.client.force_login(make_recruiter())

    def test_buttons_for_each_of_the_eight_stages(self):
        for stage, actions in self.EXPECTED.items():
            with self.subTest(stage=stage):
                application = make_application(stage=stage)
                response = self.client.get(application.get_absolute_url())
                html = response.content.decode()
                self.assertIn('id="stage-card"', html)
                self.assertEqual(posted_actions(html), actions)
                self.assertEqual(
                    html.count(f'name="expected_stage" value="{stage.value}"'), len(actions)
                )

    def test_buttons_name_the_destination_and_post_with_htmx(self):
        application = make_application(stage=Stage.OFFER)
        response = self.client.get(application.get_absolute_url())
        url = transition_url(application)
        self.assertContains(response, "Advance to Hired")
        self.assertContains(response, "Back to Final Review")
        self.assertContains(response, f'action="{url}"', count=2)
        self.assertContains(response, f'hx-post="{url}"', count=2)
        self.assertContains(response, 'hx-target="#stage-card"', count=2)
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
        self.assertEqual(posted_actions(response.content.decode()), [])
