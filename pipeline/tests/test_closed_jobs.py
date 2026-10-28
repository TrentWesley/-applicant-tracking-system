"""Phase 7: what closing and reopening a job means for its applications (AC12, AC13, AC25)."""

from django.test import TestCase
from django.urls import reverse

from candidates.tests.utils import make_candidate
from core.tests.utils import make_recruiter
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.forms import CLOSED_JOB_CHOICE_MESSAGE
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE, Application, Stage, StageChange
from pipeline.services import JOB_CLOSED_MESSAGE, StageChangeRefused, create_application
from pipeline.tests.utils import make_application

CREATE_URL = reverse("pipeline:application_create")
HTMX = {"HTTP_HX_REQUEST": "true"}


class ClosedJobTestCase(TestCase):
    """The job is closed through its real Close action, as a Recruiter would."""

    def setUp(self):
        self.recruiter = make_recruiter()
        self.client.force_login(self.recruiter)
        self.job = make_job()

    def close(self):
        self.client.post(reverse("jobs:job_close", args=[self.job.pk]))
        self.assertEqual(self.job_status(), JobStatus.CLOSED)

    def reopen(self):
        self.client.post(reverse("jobs:job_reopen", args=[self.job.pk]))
        self.assertEqual(self.job_status(), JobStatus.OPEN)

    def job_status(self):
        return JobOpening.objects.get(pk=self.job.pk).status

    def transition(self, application, action, note=""):
        application.refresh_from_db()
        return self.client.post(
            reverse("pipeline:application_transition", args=[application.pk]),
            {"action": action, "expected_stage": application.stage, "note": note},
            **HTMX,
        )

    def create_through_form(self, candidate):
        return self.client.post(
            CREATE_URL, {"candidate": candidate.pk, "job_opening": self.job.pk, "notes": ""}
        )


class NewApplicationsOnClosedJobsTests(ClosedJobTestCase):
    def test_closing_blocks_new_applications(self):
        # AC12
        self.close()
        response = self.create_through_form(make_candidate("new@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors["job_opening"], [CLOSED_JOB_CHOICE_MESSAGE]
        )
        with self.assertRaisesMessage(StageChangeRefused, JOB_CLOSED_MESSAGE):
            create_application(
                candidate=make_candidate("other@example.com"),
                job_opening=self.job,
                created_by=self.recruiter,
            )
        self.assertFalse(Application.objects.exists())

    def test_the_create_form_stops_offering_a_closed_job(self):
        self.close()
        self.assertNotContains(self.client.get(CREATE_URL), f'value="{self.job.pk}"')
        self.reopen()
        self.assertContains(self.client.get(CREATE_URL), f'value="{self.job.pk}"')

    def test_reopening_allows_new_applications_but_not_duplicates(self):
        # AC13
        existing = make_application(job=self.job, stage=Stage.INTERVIEW)
        self.close()
        self.reopen()
        response = self.create_through_form(make_candidate("new@example.com"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.job.applications.count(), 2)
        response = self.create_through_form(existing.candidate)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_APPLICATION_MESSAGE.replace("'", "&#x27;"))
        self.assertEqual(self.job.applications.count(), 2)
        existing.refresh_from_db()
        self.assertEqual(existing.stage, Stage.INTERVIEW)
        self.assertEqual(existing.stage_changes.count(), 1)


class MovesOnClosedJobsTests(ClosedJobTestCase):
    """AC12: existing applications on a closed job keep moving under the usual rules."""

    def test_advance_back_reject_and_withdraw(self):
        moving = make_application(job=self.job, stage=Stage.SCREENING)
        rejected = make_application(job=self.job, stage=Stage.INTERVIEW)
        withdrawn = make_application(job=self.job, stage=Stage.OFFER)
        self.close()
        self.assertContains(
            self.transition(moving, "advance"), "Moved from Screening to Interview."
        )
        self.assertContains(self.transition(moving, "back"), "Moved from Interview to Screening.")
        self.assertContains(self.transition(rejected, "reject", "No."), "to Rejected.")
        self.assertContains(self.transition(withdrawn, "withdraw", "Left."), "to Withdrawn.")
        self.assertEqual(StageChange.objects.count(), 3 + 4)
        self.assertEqual(self.job_status(), JobStatus.CLOSED)

    def test_hiring_on_a_closed_job_works_and_leaves_it_closed(self):
        application = make_application(job=self.job, stage=Stage.OFFER)
        self.close()
        self.assertContains(self.transition(application, "advance"), "Moved from Offer to Hired.")
        self.assertEqual(self.job_status(), JobStatus.CLOSED)

    def test_the_usual_rules_still_apply(self):
        application = make_application(job=self.job)
        self.close()
        self.assertContains(self.transition(application, "back"), "isn&#x27;t allowed")
        self.assertContains(self.transition(application, "reject"), "A note is required")
        self.assertEqual(application.stage_changes.count(), 1)

    def test_the_stage_card_still_offers_moves(self):
        application = make_application(job=self.job, stage=Stage.INTERVIEW)
        self.close()
        response = self.client.get(application.get_absolute_url())
        self.assertContains(response, "Advance to Final Review")
        self.assertContains(response, "?confirm=reject")
        self.assertContains(response, ">Job Closed<")

    def test_history_stays_complete_and_visible(self):
        application = make_application(job=self.job)
        self.transition(application, "advance")
        self.close()
        response = self.client.get(application.get_absolute_url())
        self.assertEqual(len(response.context["history"]), 2)
        self.assertContains(response, "New application")


class ReactivateOnClosedJobsTests(ClosedJobTestCase):
    def test_walkthrough_6_misclicked_reject_on_a_closed_job(self):
        # AC25 (closed-job part): undo with one Reactivate; the job stays Closed and still
        # refuses new applicants.
        application = make_application(job=self.job, stage=Stage.FINAL_REVIEW)
        self.close()
        self.transition(application, "reject", "Wrong candidate.")
        before = StageChange.objects.count()
        response = self.transition(application, "reactivate", "Rejected by mistake.")
        self.assertContains(response, "Moved from Rejected to Final Review.")
        self.assertEqual(StageChange.objects.count(), before + 1)
        self.assertEqual(self.job_status(), JobStatus.CLOSED)
        response = self.create_through_form(make_candidate("late@example.com"))
        self.assertEqual(
            response.context["form"].errors["job_opening"], [CLOSED_JOB_CHOICE_MESSAGE]
        )


class JobClosedBadgeOnApplicationsTests(ClosedJobTestCase):
    def test_application_list_marks_only_applications_on_closed_jobs(self):
        on_closed = make_application(job=self.job)
        on_open = make_application(job=make_job("Data Engineer"))
        self.close()
        html = self.client.get(reverse("pipeline:application_list")).content.decode()
        rows = {
            application: html[html.index(application.get_absolute_url()) :].split("</tr>")[0]
            for application in (on_closed, on_open)
        }
        self.assertIn(">Job Closed<", rows[on_closed])
        self.assertNotIn("Job Closed", rows[on_open])

    def test_stage_filter_shows_the_badge_too(self):
        make_application(job=self.job, stage=Stage.OFFER)
        self.close()
        response = self.client.get(reverse("pipeline:application_list"), {"stage": "offer"})
        self.assertContains(response, ">Job Closed<", count=1)
