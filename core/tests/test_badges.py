"""
Phase 13: shared badges everywhere (US 60; AC44). Awaiting Decision marks an application whose
current stage is Offer and nothing else; Job Closed marks a closed job and its applications.
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.utils import database_state, make_recruiter
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import ACTIVE_STAGES, Stage
from pipeline.services import change_stage
from pipeline.tests.utils import make_application

AWAITING = "Awaiting Decision"
CLOSED = "Job Closed"


def pages_showing(application):
    """Every page on which this application, or its job, appears."""
    return {
        "application list": reverse("pipeline:application_list"),
        "offer filter": f"{reverse('pipeline:application_list')}?stage={application.stage}",
        "application detail": application.get_absolute_url(),
        "candidate detail": application.candidate.get_absolute_url(),
        "job detail": application.job_opening.get_absolute_url(),
        "dashboard": reverse("core:dashboard"),
    }


def move(application, action, note=""):
    change_stage(
        application=application,
        action=action,
        expected_stage=application.stage,
        changed_by=application.created_by,
        note=note,
    )
    application.refresh_from_db()


class BadgeTestCase(TestCase):
    def setUp(self):
        self.client.force_login(make_recruiter())

    def count_on(self, url, text):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertTemplateUsed(response, "base.html")  # AC44: the sidebar layout
        return response.content.decode().count(text)


class AwaitingDecisionTests(BadgeTestCase):
    def test_an_offer_application_is_marked_once_on_every_page(self):
        application = make_application(stage=Stage.OFFER)
        for page, url in pages_showing(application).items():
            with self.subTest(page=page):
                self.assertEqual(self.count_on(url, AWAITING), 1)

    def test_it_appears_right_after_the_offer_stage_badge(self):
        make_application(stage=Stage.OFFER)
        response = self.client.get(reverse("pipeline:application_list"))
        self.assertRegex(
            response.content.decode(), rf'>Offer</span>\s*<span class="badge [^"]+">{AWAITING}<'
        )

    def test_no_other_stage_is_marked(self):
        for stage in Stage:
            if stage == Stage.OFFER:
                continue
            with self.subTest(stage=stage):
                application = make_application(stage=stage)
                for page, url in pages_showing(application).items():
                    self.assertEqual(self.count_on(url, AWAITING), 0, page)

    def test_history_rows_at_offer_are_not_marked(self):
        # At Offer once, now back at Final Review: its history and Recent Activity show the move
        # to Offer, but it isn't awaiting a decision.
        application = make_application(stage=Stage.FINAL_REVIEW)
        move(application, "advance")
        move(application, "back")
        for page, url in pages_showing(application).items():
            with self.subTest(page=page):
                self.assertEqual(self.count_on(url, AWAITING), 0)

    def test_an_offer_on_its_detail_page_is_marked_once_despite_its_history(self):
        application = make_application(stage=Stage.FINAL_REVIEW)
        move(application, "advance")
        self.assertEqual(self.count_on(application.get_absolute_url(), AWAITING), 1)

    def test_the_htmx_stage_card_keeps_the_badge(self):
        application = make_application(stage=Stage.FINAL_REVIEW)
        response = self.client.post(
            reverse("pipeline:application_transition", args=[application.pk]),
            {"action": "advance", "expected_stage": "final_review"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, AWAITING, count=1)
        response = self.client.post(
            reverse("pipeline:application_transition", args=[application.pk]),
            {"action": "back", "expected_stage": "offer"},
            HTTP_HX_REQUEST="true",
        )
        self.assertNotContains(response, AWAITING)


class JobClosedTests(BadgeTestCase):
    def test_a_closed_job_and_its_applications_are_marked_on_every_page(self):
        application = make_application(stage=Stage.INTERVIEW)
        JobOpening.objects.filter(pk=application.job_opening_id).update(status=JobStatus.CLOSED)
        pages = pages_showing(application) | {"job list": reverse("jobs:job_list")}
        for page, url in pages.items():
            with self.subTest(page=page):
                self.assertGreaterEqual(self.count_on(url, CLOSED), 1)

    def test_the_dashboard_marks_closed_jobs_in_needs_attention_and_recent_activity(self):
        application = make_application(stage=Stage.OFFER)
        JobOpening.objects.filter(pk=application.job_opening_id).update(status=JobStatus.CLOSED)
        # Needs Attention: the closed job's row and the Offer row; Recent Activity: the creation
        # entry's row.
        self.assertEqual(self.count_on(reverse("core:dashboard"), CLOSED), 3)

    def test_open_jobs_are_never_marked(self):
        application = make_application(stage=Stage.OFFER, job=make_job())
        pages = pages_showing(application) | {"job list": reverse("jobs:job_list")}
        for page, url in pages.items():
            with self.subTest(page=page):
                self.assertEqual(self.count_on(url, CLOSED), 0)

    def test_badges_are_display_only(self):
        application = make_application(stage=Stage.OFFER)
        JobOpening.objects.filter(pk=application.job_opening_id).update(status=JobStatus.CLOSED)
        before = database_state()
        for url in pages_showing(application).values():
            self.client.get(url)
        self.assertEqual(database_state(), before)


def badge(stage):
    return render_to_string(
        "core/_stage_badge.html", {"stage": stage, "label": stage.label}
    ).strip()


class StageBadgeTests(SimpleTestCase):
    """One badge partial, styled by stage group: active, Offer, Hired, Rejected and Withdrawn."""

    def test_badge_shows_the_stage_label(self):
        for stage in Stage:
            with self.subTest(stage=stage):
                self.assertIn(f">{stage.label}</span>", badge(stage))

    def test_active_stages_before_offer_share_one_style(self):
        early = [s for s in ACTIVE_STAGES if s != Stage.OFFER]
        self.assertEqual(
            {badge(s).replace(s.label, "") for s in early},
            {badge(Stage.APPLIED).replace("Applied", "")},
        )

    def test_offer_hired_and_closed_out_stages_each_look_different(self):
        groups = {
            badge(Stage.APPLIED).replace("Applied", ""),
            badge(Stage.OFFER).replace("Offer", ""),
            badge(Stage.HIRED).replace("Hired", ""),
            badge(Stage.REJECTED).replace("Rejected", ""),
        }
        self.assertEqual(len(groups), 4)
        self.assertEqual(
            badge(Stage.REJECTED).replace("Rejected", ""),
            badge(Stage.WITHDRAWN).replace("Withdrawn", ""),
        )
