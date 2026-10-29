"""Phase 12: the dashboard (US 55-58; AC40-AC43)."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from candidates.services import archive_candidate
from candidates.tests.utils import make_candidate
from core.tests.utils import PASSWORD, database_state, make_admin, make_recruiter, make_user
from jobs.models import JobOpening, JobStatus
from jobs.tests.utils import make_job
from pipeline.models import Application, Stage, StageChange
from pipeline.services import change_stage
from pipeline.tests.utils import make_application

DASHBOARD = reverse("core:dashboard")
LIST_URL = reverse("pipeline:application_list")

# The UI prototype's sample data: 7 jobs (3 closed) and 36 applications.
JOBS = {
    1: ("Backend Developer", JobStatus.OPEN),
    2: ("Data Analyst", JobStatus.OPEN),
    3: ("Product Designer", JobStatus.CLOSED),
    4: ("IT Support Specialist", JobStatus.CLOSED),
    5: ("Marketing Coordinator", JobStatus.OPEN),
    6: ("HR Generalist", JobStatus.CLOSED),
    7: ("Sales Development Rep", JobStatus.OPEN),
}
APPLICATIONS = [
    ("Ava Thompson", 1, Stage.APPLIED),
    ("Noah Patel", 1, Stage.APPLIED),
    ("Mia Rodriguez", 2, Stage.APPLIED),
    ("Liam Chen", 5, Stage.APPLIED),
    ("Sofia Nguyen", 7, Stage.APPLIED),
    ("Ethan Brooks", 7, Stage.APPLIED),
    ("Zoe Kim", 2, Stage.APPLIED),
    ("Lucas Rivera", 5, Stage.APPLIED),
    ("Isabella Ortiz", 1, Stage.SCREENING),
    ("Mason Lee", 2, Stage.SCREENING),
    ("Harper Wilson", 3, Stage.SCREENING),
    ("Elijah Davis", 7, Stage.SCREENING),
    ("Amelia Clark", 5, Stage.SCREENING),
    ("James Wright", 1, Stage.SCREENING),
    ("Charlotte Hall", 1, Stage.INTERVIEW),
    ("Benjamin Young", 3, Stage.INTERVIEW),
    ("Evelyn King", 2, Stage.INTERVIEW),
    ("Henry Scott", 4, Stage.INTERVIEW),
    ("Aria Green", 7, Stage.INTERVIEW),
    ("Jack Adams", 1, Stage.FINAL_REVIEW),
    ("Luna Baker", 2, Stage.FINAL_REVIEW),
    ("Daniel Turner", 5, Stage.FINAL_REVIEW),
    ("Grace Hill", 1, Stage.OFFER),
    ("Samuel Moore", 3, Stage.OFFER),
    ("Chloe Allen", 7, Stage.OFFER),
    ("Owen Carter", 6, Stage.HIRED),
    ("Lily Evans", 6, Stage.HIRED),
    ("Leo Mitchell", 4, Stage.HIRED),
    ("Ella Perez", 2, Stage.HIRED),
    ("Wyatt Roberts", 1, Stage.REJECTED),
    ("Nora Phillips", 3, Stage.REJECTED),
    ("Jacob Campbell", 4, Stage.REJECTED),
    ("Hazel Parker", 5, Stage.REJECTED),
    ("Caleb Edwards", 2, Stage.REJECTED),
    ("Stella Collins", 1, Stage.WITHDRAWN),
    ("Julian Stewart", 7, Stage.WITHDRAWN),
]
# Archived after reaching a final stage: a hire still counts; nothing else does.
ARCHIVED = ("Leo Mitchell", "Owen Carter", "Jacob Campbell")
# Offer applications, oldest at Offer first (the order Needs Attention lists them in).
OFFER_ORDER = ("Samuel Moore", "Chloe Allen", "Grace Hill")


def close(*jobs):
    """Test setup: close jobs after their applications exist (a closed job accepts none)."""
    JobOpening.objects.filter(pk__in=[job.pk for job in jobs]).update(status=JobStatus.CLOSED)


def build_prototype_dataset():
    jobs = {key: make_job(title, department="Dept") for key, (title, _) in JOBS.items()}
    applications = {}
    for number, (name, job_key, stage) in enumerate(APPLICATIONS, start=1):
        first, last = name.split()
        candidate = make_candidate(
            email=f"applicant{number}@example.com", first_name=first, last_name=last
        )
        applications[name] = make_application(candidate=candidate, job=jobs[job_key], stage=stage)
    close(*(jobs[key] for key, (_, status) in JOBS.items() if status == JobStatus.CLOSED))
    for name in ARCHIVED:
        archive_candidate(applications[name].candidate)
    now = timezone.now()
    for days, name in enumerate(reversed(OFFER_ORDER), start=1):
        Application.objects.filter(pk=applications[name].pk).update(
            stage_changed_at=now - timedelta(days=days)
        )
    return jobs, applications


def needs_attention(response):
    """The Needs Attention section's HTML (names can also appear under Recent Activity)."""
    return response.content.decode().split('id="needs-attention"')[1].split("</section>")[0]


class DashboardTestCase(TestCase):
    def setUp(self):
        self.user = make_recruiter("rita", first_name="Rita", last_name="Moreno")
        self.client.force_login(self.user)

    def get(self):
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200)
        return response


class PrototypeDatasetTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.jobs, self.applications = build_prototype_dataset()

    def test_summary_counts(self):
        # AC40: 4 open jobs; 25 active applications, 4 of them on closed jobs; 4 hires, one on
        # a closed job and two for archived candidates.
        summary = self.get().context["summary"]
        self.assertEqual(
            (summary.open_jobs, summary.closed_jobs, summary.active, summary.hires),
            (4, 3, 25, 4),
        )

    def test_summary_tiles_render(self):
        response = self.get()
        self.assertContains(response, "Open job openings")
        self.assertContains(response, '<div class="stat-value">4</div>', count=2)  # jobs, hires
        self.assertContains(response, '<div class="stat-value text-primary">25</div>')

    def test_pipeline_counts_and_links(self):
        # AC41: one card per active stage, linking to the stage-filtered list.
        pipeline = self.get().context["pipeline"]
        expected = [
            (Stage.APPLIED, 8),
            (Stage.SCREENING, 6),
            (Stage.INTERVIEW, 5),
            (Stage.FINAL_REVIEW, 3),
            (Stage.OFFER, 3),
        ]
        self.assertEqual([(card.stage, card.count) for card in pipeline], expected)
        response = self.get()
        for stage, count in expected:
            with self.subTest(stage=stage):
                url = f"{LIST_URL}?stage={stage.value}"
                self.assertContains(response, f'href="{url}"', count=1)
                listed = self.client.get(url).context["applications"]
                self.assertEqual(len(listed), count)

    def test_pipeline_bars_are_scaled_to_the_largest_stage(self):
        response = self.get()
        self.assertContains(response, 'value="8" max="8"')
        self.assertContains(response, 'value="3" max="8"', count=2)

    def test_needs_attention_closed_jobs_with_active_applications(self):
        # AC42: HR Generalist is closed but has only hires, so it isn't listed.
        closed = self.get().context["closed_jobs"]
        self.assertEqual(
            [(job.title, job.active_count) for job in closed],
            [("Product Designer", 3), ("IT Support Specialist", 1)],
        )
        response = self.get()
        self.assertContains(response, f'href="{self.jobs[3].get_absolute_url()}"')
        self.assertContains(response, "3 active applications")
        self.assertContains(response, "1 active application <span")
        self.assertNotIn("HR Generalist", needs_attention(response))

    def test_needs_attention_offers_longest_waiting_first(self):
        offers = self.get().context["offers"]
        self.assertEqual([str(a.candidate) for a in offers], list(OFFER_ORDER))
        response = self.get()
        for name in OFFER_ORDER:
            self.assertContains(response, f'href="{self.applications[name].get_absolute_url()}"')

    def test_an_offer_on_a_closed_job_shows_job_closed(self):
        # Phase 13: both closed-job rows, plus Samuel Moore's Offer on Product Designer.
        self.assertEqual(needs_attention(self.get()).count("Job Closed"), 3)

    def test_recent_activity_shows_the_ten_newest(self):
        response = self.get()
        self.assertEqual(len(response.context["recent_activity"]), 10)

    def test_a_dashboard_request_changes_nothing_and_only_reads(self):
        before = database_state()
        with CaptureQueriesContext(connection) as queries:
            self.get()
        self.assertEqual(database_state(), before)
        writes = [q["sql"] for q in queries if not q["sql"].lstrip().upper().startswith("SELECT")]
        self.assertEqual(writes, [])


class CountRulesTests(DashboardTestCase):
    """Edge cases for each count: closed jobs, archived candidates, terminal stages."""

    def test_active_applications_on_closed_jobs_count(self):
        job = make_job()
        make_application(job=job, stage=Stage.INTERVIEW)
        close(job)
        summary = self.get().context["summary"]
        self.assertEqual((summary.open_jobs, summary.active), (0, 1))

    def test_terminal_stages_are_not_active(self):
        for stage in (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN):
            make_application(stage=stage)
        response = self.get()
        self.assertEqual(response.context["summary"].active, 0)
        self.assertEqual([c.count for c in response.context["pipeline"]], [0] * 5)
        self.assertEqual(response.context["summary"].hires, 1)

    def test_hires_count_on_closed_jobs_and_for_archived_candidates(self):
        hired = make_application(stage=Stage.HIRED)
        close(hired.job_opening)
        archive_candidate(hired.candidate)
        make_application(stage=Stage.HIRED)
        self.assertEqual(self.get().context["summary"].hires, 2)

    def test_a_closed_job_with_only_final_applications_needs_no_attention(self):
        job = make_job()
        for stage in (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN):
            make_application(job=job, stage=stage)
        close(job)
        self.assertEqual(list(self.get().context["closed_jobs"]), [])

    def test_an_open_job_with_active_applications_needs_no_attention(self):
        make_application(job=make_job(), stage=Stage.INTERVIEW)
        self.assertEqual(list(self.get().context["closed_jobs"]), [])

    def test_closed_jobs_order_by_active_count_then_title(self):
        jobs = {t: make_job(t) for t in ("Zeta", "Alpha", "Mid")}
        for title, count in (("Zeta", 2), ("Alpha", 1), ("Mid", 2)):
            for _ in range(count):
                make_application(job=jobs[title], stage=Stage.SCREENING)
        make_application(job=jobs["Alpha"], stage=Stage.REJECTED)  # not counted
        close(*jobs.values())
        closed = self.get().context["closed_jobs"]
        self.assertEqual(
            [(j.title, j.active_count) for j in closed], [("Mid", 2), ("Zeta", 2), ("Alpha", 1)]
        )

    def test_offers_with_the_same_time_order_by_pk(self):
        first = make_application(stage=Stage.OFFER)
        second = make_application(stage=Stage.OFFER)
        Application.objects.update(stage_changed_at=timezone.now())
        self.assertEqual(list(self.get().context["offers"]), [first, second])

    def test_reopening_a_job_removes_it_from_needs_attention(self):
        job = make_job()
        make_application(job=job, stage=Stage.OFFER)
        close(job)
        self.assertEqual(len(self.get().context["closed_jobs"]), 1)
        JobOpening.objects.filter(pk=job.pk).update(status=JobStatus.OPEN)
        self.assertEqual(len(self.get().context["closed_jobs"]), 0)
        self.assertEqual(len(self.get().context["offers"]), 1)  # still at Offer


class RecentActivityTests(DashboardTestCase):
    """AC43: the 10 most recent StageChanges, newest first, from the stored history."""

    def setUp(self):
        super().setUp()
        self.mover = make_recruiter("mo", first_name="Morgan", last_name="Reyes")
        self.base = timezone.now() - timedelta(days=1)

    def at(self, minutes):
        return mock.patch(
            "django.utils.timezone.now", return_value=self.base + timedelta(minutes=minutes)
        )

    def make_history(self):
        """12 StageChanges: 6 creations, then 6 moves whose times are out of pk order."""
        applications = []
        for minute in range(6):
            with self.at(minute):
                applications.append(make_application(created_by=self.mover))
        # Later rows get earlier times, so ordering by pk would give the wrong answer.
        for offset, application in zip((60, 50, 40, 30, 20, 10), applications, strict=True):
            with self.at(offset):
                change_stage(
                    application=application,
                    action="advance",
                    expected_stage="applied",
                    changed_by=self.mover,
                    note=f"note {offset}",
                )
        return applications

    def test_exactly_the_ten_newest_render_newest_first(self):
        self.make_history()
        self.assertEqual(StageChange.objects.count(), 12)
        expected = list(StageChange.objects.order_by("-changed_at", "-pk")[:10])
        recent = list(self.get().context["recent_activity"])
        self.assertEqual(recent, expected)
        self.assertEqual(recent[0].note, "note 60")
        oldest_two = StageChange.objects.order_by("changed_at", "pk")[:2]
        for change in oldest_two:
            self.assertNotIn(change, recent)

    def test_each_row_shows_when_application_change_by_and_note(self):
        applications = self.make_history()
        response = self.get()
        self.assertContains(response, f'href="{applications[0].get_absolute_url()}"')
        self.assertContains(response, "Morgan Reyes")
        self.assertContains(response, "note 60")
        self.assertContains(response, "New")  # creation entries have no from stage
        self.assertContains(response, ">Screening</span>")

    def test_a_deactivated_users_name_still_shows(self):
        self.make_history()
        User.objects.filter(pk=self.mover.pk).update(is_active=False)
        self.assertContains(self.get(), "Morgan Reyes")

    def test_viewing_the_dashboard_never_changes_history(self):
        self.make_history()
        before = list(StageChange.objects.order_by("pk").values_list())
        self.get()
        self.get()
        self.assertEqual(list(StageChange.objects.order_by("pk").values_list()), before)


class QueryCountTests(DashboardTestCase):
    def test_query_count_does_not_grow_with_the_data(self):
        # No per-row lookups: the same queries run for an empty database and the full dataset.
        with CaptureQueriesContext(connection) as empty:
            self.get()
        build_prototype_dataset()
        with CaptureQueriesContext(connection) as full:
            self.get()
        self.assertEqual(len(full), len(empty), [q["sql"] for q in full])


class EmptyDashboardTests(DashboardTestCase):
    def test_every_section_has_an_empty_state(self):
        response = self.get()
        summary = response.context["summary"]
        self.assertEqual((summary.open_jobs, summary.active, summary.hires), (0, 0, 0))
        self.assertContains(response, "No closed jobs have active applications.")
        self.assertContains(response, "No applications are at Offer.")
        self.assertContains(response, "No stage changes yet.")
        self.assertContains(response, 'value="0" max="1"', count=5)  # empty bars, no divide by zero


class DashboardAccessTests(TestCase):
    def test_both_roles_land_on_the_dashboard_after_login(self):
        for user in (make_recruiter(), make_admin()):
            with self.subTest(role=user.username):
                response = self.client.post(
                    reverse("login"), {"username": user.username, "password": PASSWORD}, follow=True
                )
                self.assertRedirects(response, DASHBOARD)
                self.assertTemplateUsed(response, "core/dashboard.html")
                self.client.logout()

    def test_both_roles_see_the_same_numbers(self):
        make_application(stage=Stage.OFFER)
        summaries = []
        for user in (make_recruiter(), make_admin()):
            self.client.force_login(user)
            summaries.append(self.client.get(DASHBOARD).context["summary"])
        self.assertEqual(summaries[0], summaries[1])

    def test_a_user_without_a_role_gets_403(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(self.client.get(DASHBOARD).status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        self.assertRedirects(self.client.get(DASHBOARD), f"{reverse('login')}?next=/")
