from unittest import mock

from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import TestCase
from django.urls import get_resolver, reverse
from django.utils import dateformat, timezone

from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.models import JobStatus
from jobs.tests.utils import make_job
from pipeline.forms import ARCHIVED_CANDIDATE_CHOICE_MESSAGE, CLOSED_JOB_CHOICE_MESSAGE
from pipeline.models import DUPLICATE_APPLICATION_MESSAGE, Application, Stage, StageChange
from pipeline.services import StageChangeRefused
from pipeline.tests.utils import make_application

LIST_URL = reverse("pipeline:application_list")
CREATE_URL = reverse("pipeline:application_create")


def detail_url(application):
    return reverse("pipeline:application_detail", args=[application.pk])


def make_viewer():
    """A staff user who may only view applications."""
    user = make_user("viewer")
    user.user_permissions.add(Permission.objects.get(codename="view_application"))
    return user


class StaffTestCase(TestCase):
    def setUp(self):
        self.staff = [make_recruiter(), make_admin()]


class ApplicationListTests(StaffTestCase):
    def test_recruiter_and_admin_see_applications_with_stage_badges(self):
        candidate = make_candidate(first_name="Ann", last_name="Lee")
        job = make_job("Data Analyst")
        application = make_application(candidate, job, stage=Stage.FINAL_REVIEW)
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(LIST_URL)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pipeline/application_list.html")
                self.assertTemplateUsed(response, "core/_stage_badge.html")
                self.assertContains(response, "<h1", count=1)
                self.assertContains(response, "Applications</h1>")
                self.assertContains(response, f'href="{detail_url(application)}"')
                self.assertContains(response, f'href="{job.get_absolute_url()}"')
                self.assertContains(response, "Ann Lee")
                self.assertContains(response, ">Final Review</span>")

    def test_empty_list_says_so(self):
        self.client.force_login(self.staff[0])
        self.assertContains(self.client.get(LIST_URL), "No applications yet.")

    def test_new_application_button_for_users_who_can_add(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(LIST_URL), f'href="{CREATE_URL}"')

    def test_new_application_button_hidden_from_view_only_users(self):
        self.client.force_login(make_viewer())
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{CREATE_URL}"')


class ApplicationStageFilterTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.open_job, self.closed_job = make_job("Analyst"), make_job("Engineer")
        self.applied_open = make_application(make_candidate("a@x.com"), self.open_job)
        self.applied_closed = make_application(make_candidate("b@x.com"), self.closed_job)
        self.offer = make_application(make_candidate("c@x.com"), self.open_job, stage=Stage.OFFER)
        self.closed_job.status = JobStatus.CLOSED
        self.closed_job.save()
        self.client.force_login(self.staff[0])

    def applications_for(self, query):
        response = self.client.get(LIST_URL, query)
        self.assertEqual(response.status_code, 200)
        return set(response.context["applications"])

    def test_stage_filter_covers_open_and_closed_jobs_and_only_that_stage(self):
        self.assertEqual(
            self.applications_for({"stage": Stage.APPLIED}),
            {self.applied_open, self.applied_closed},
        )
        self.assertEqual(self.applications_for({"stage": Stage.OFFER}), {self.offer})

    def test_no_filter_or_an_unknown_stage_shows_everything(self):
        everything = {self.applied_open, self.applied_closed, self.offer}
        self.assertEqual(self.applications_for({}), everything)
        self.assertEqual(self.applications_for({"stage": "promoted"}), everything)

    def test_a_stage_with_no_applications_says_so(self):
        response = self.client.get(LIST_URL, {"stage": Stage.HIRED})
        self.assertContains(response, "No applications at Hired.")

    def test_filter_links_cover_every_stage_and_mark_the_current_one(self):
        response = self.client.get(LIST_URL, {"stage": Stage.OFFER})
        for stage in Stage:
            self.assertContains(response, f'href="{LIST_URL}?stage={stage.value}"')
        self.assertContains(
            response,
            f'href="{LIST_URL}?stage=offer" class="btn btn-sm btn-active" aria-current="page"',
        )
        self.assertContains(response, f'href="{LIST_URL}" class="btn btn-sm"')  # "All"


class ApplicationCreateTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(first_name="Ann", last_name="Lee")
        self.job = make_job("Data Analyst")

    def data(self, **extra):
        return {"candidate": self.candidate.pk, "job_opening": self.job.pk, "notes": ""} | extra

    def assert_nothing_written(self):
        self.assertFalse(Application.objects.exists())
        self.assertFalse(StageChange.objects.exists())

    def test_form_page_renders_labelled_fields_and_no_stage(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New application</h1>")
        for field in ("candidate", "job_opening", "notes"):
            self.assertContains(response, f'<label for="id_{field}"')
        self.assertNotContains(response, 'name="stage"')
        self.assertContains(response, "starts at Applied")

    def test_candidate_query_parameter_preselects_that_candidate(self):
        make_candidate("other@example.com")
        self.client.force_login(self.staff[0])
        response = self.client.get(CREATE_URL, {"candidate": self.candidate.pk})
        self.assertContains(response, f'<option value="{self.candidate.pk}" selected>')
        self.assertContains(response, f'href="{self.candidate.get_absolute_url()}"')  # back link

    def test_preselected_candidate_can_be_changed(self):
        other = make_candidate("other@example.com")
        self.client.force_login(self.staff[0])
        self.client.post(
            f"{CREATE_URL}?candidate={self.candidate.pk}", self.data(candidate=other.pk)
        )
        self.assertEqual(Application.objects.get().candidate, other)

    def test_an_archived_or_unknown_preselected_candidate_is_not_selected(self):
        archived = make_candidate("gone@example.com", archived_at=timezone.now())
        self.client.force_login(self.staff[0])
        for value in (archived.pk, 999999, "abc"):
            with self.subTest(value=value):
                response = self.client.get(CREATE_URL, {"candidate": value})
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["form"]["candidate"].value())
                self.assertNotContains(response, f'<option value="{archived.pk}"')

    def test_recruiter_and_admin_create_at_applied_and_land_on_detail(self):
        for index, user in enumerate(self.staff):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                job = make_job(f"Role {index}")
                response = self.client.post(
                    CREATE_URL, self.data(job_opening=job.pk, notes="Strong SQL."), follow=True
                )
                application = Application.objects.get(job_opening=job)
                self.assertRedirects(response, detail_url(application))
                self.assertContains(response, f"Application created: Ann Lee for Role {index}.")
                self.assertEqual(application.stage, Stage.APPLIED)
                self.assertEqual(application.created_by, user)
                self.assertEqual(application.notes, "Strong SQL.")
                entry = application.stage_changes.get()
                self.assertEqual((entry.from_stage, entry.to_stage), (None, Stage.APPLIED))
                self.assertEqual(entry.changed_by, user)

    def test_posted_stage_is_ignored(self):
        self.client.force_login(self.staff[0])
        self.client.post(CREATE_URL, self.data(stage=Stage.HIRED))
        self.assertEqual(Application.objects.get().stage, Stage.APPLIED)

    def test_closed_job_is_refused_and_nothing_is_written(self):
        self.job.status = JobStatus.CLOSED
        self.job.save()
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Closed jobs don&#x27;t accept new applications.")
        self.assertEqual(
            response.context["form"].errors["job_opening"], [CLOSED_JOB_CHOICE_MESSAGE]
        )
        self.assert_nothing_written()

    def test_archived_candidate_is_refused_and_nothing_is_written(self):
        self.candidate.archived_at = timezone.now()
        self.candidate.save()
        self.client.force_login(self.staff[0])
        response = self.client.post(f"{CREATE_URL}?candidate={self.candidate.pk}", self.data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors["candidate"], [ARCHIVED_CANDIDATE_CHOICE_MESSAGE]
        )
        self.assert_nothing_written()

    def test_duplicate_pair_is_refused_with_a_message(self):
        existing = make_application(self.candidate, self.job)
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_APPLICATION_MESSAGE)
        self.assertEqual(list(Application.objects.all()), [existing])
        self.assertEqual(StageChange.objects.count(), 1)

    def test_a_refusal_from_the_service_is_shown_on_the_form(self):
        # The form saw an open job, but the service found it closed inside its transaction.
        self.client.force_login(self.staff[0])
        refusal = StageChangeRefused("This job is closed and isn't accepting new applications.")
        with mock.patch("pipeline.views.create_application", side_effect=refusal):
            response = self.client.post(CREATE_URL, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(
            response, "This job is closed and isn&#x27;t accepting new applications."
        )
        self.assert_nothing_written()

    def test_a_failed_history_write_during_the_post_leaves_nothing_behind(self):
        self.client.force_login(self.staff[0])
        with (
            mock.patch.object(StageChange.objects, "create", side_effect=DatabaseError("disk")),
            self.assertRaises(DatabaseError),
        ):
            self.client.post(CREATE_URL, self.data())
        self.assert_nothing_written()

    def test_missing_fields_are_refused(self):
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, {"notes": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assert_nothing_written()


class ApplicationDetailTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.creator = make_recruiter("rita", first_name="Rita", last_name="Ng")
        self.candidate = make_candidate(first_name="Ann", last_name="Lee")
        self.job = make_job("Data Analyst")
        self.application = make_application(
            self.candidate, self.job, created_by=self.creator, notes="Strong SQL background."
        )

    def test_detail_shows_stage_people_job_and_notes(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url(self.application))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pipeline/application_detail.html")
                self.assertContains(response, "Ann Lee for Data Analyst</h1>")
                self.assertContains(response, f'href="{self.candidate.get_absolute_url()}"')
                self.assertContains(response, f'href="{self.job.get_absolute_url()}"')
                self.assertContains(response, ">Applied</span>")
                self.assertContains(response, "Strong SQL background.")
                self.assertContains(response, "Rita Ng")

    def test_history_lists_every_entry_oldest_first(self):
        created = self.application.stage_changes.get()
        later = created.changed_at + timezone.timedelta(hours=1)
        StageChange.objects.create(
            application=self.application,
            from_stage=Stage.APPLIED,
            to_stage=Stage.SCREENING,
            changed_by=self.staff[0],
            changed_at=later + timezone.timedelta(hours=1),
            note="Second move",
        )
        StageChange.objects.create(
            application=self.application,
            from_stage=Stage.SCREENING,
            to_stage=Stage.APPLIED,
            changed_by=self.staff[0],
            changed_at=later,
            note="First move",
        )
        self.client.force_login(self.staff[0])
        response = self.client.get(detail_url(self.application))
        self.assertEqual(
            list(response.context["history"]),
            list(StageChange.objects.filter(application=self.application).order_by("changed_at")),
        )
        html = response.content.decode()
        self.assertLess(html.index("New application"), html.index("First move"))
        self.assertLess(html.index("First move"), html.index("Second move"))

    def test_history_shows_from_to_who_when_and_note(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(detail_url(self.application))
        entry = self.application.stage_changes.get()
        self.assertContains(response, "<caption", count=1)
        self.assertContains(response, "New application")  # the creation entry has no from-stage
        self.assertContains(
            response, dateformat.format(timezone.localtime(entry.changed_at), "M j, Y")
        )
        self.assertContains(response, ">Applied</span>")
        self.assertContains(response, "Rita Ng")

    def test_history_is_read_only_on_the_detail_page(self):
        # Stage moves (Phase 5) post to the transition URL; nothing edits the history itself.
        self.client.force_login(self.staff[0])
        html = self.client.get(detail_url(self.application)).content.decode()
        start = html.index('id="stage-history"')
        history = html[start : html.index("</section>", start)]
        self.assertNotIn("<form", history)
        self.assertNotIn("<input", history)
        self.assertEqual(self.client.post(detail_url(self.application)).status_code, 405)

    def test_unknown_application_is_404(self):
        self.client.force_login(self.staff[0])
        self.assertEqual(self.client.get("/applications/999999/").status_code, 404)


class NoStageChangeScreensTests(TestCase):
    def test_no_url_creates_edits_or_deletes_stage_history(self):
        names = set()
        for namespace, (_prefix, resolver) in get_resolver().namespace_dict.items():
            names |= {f"{namespace}:{n}" for n in resolver.reverse_dict if isinstance(n, str)}
        self.assertEqual(
            {name for name in names if name.startswith("pipeline:")},
            {
                "pipeline:application_list",
                "pipeline:application_create",
                "pipeline:application_detail",
                "pipeline:application_transition",
            },
        )
        self.assertFalse({n for n in names if "stage" in n.lower() or "history" in n.lower()})


class ApplicationPermissionTests(TestCase):
    def setUp(self):
        self.application = make_application()
        self.data = {
            "candidate": make_candidate("new@example.com").pk,
            "job_opening": make_job("Other").pk,
        }

    def urls(self):
        return [LIST_URL, CREATE_URL, detail_url(self.application)]

    def test_user_without_permissions_gets_403_everywhere(self):
        self.client.force_login(make_user("nobody"))
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_forbidden_create_writes_nothing(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.post(CREATE_URL, self.data).status_code, 403)
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(StageChange.objects.count(), 1)

    def test_view_only_user_can_view_but_not_create(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.get(LIST_URL).status_code, 200)
        self.assertEqual(self.client.get(detail_url(self.application)).status_code, 200)
        self.assertEqual(self.client.get(CREATE_URL).status_code, 403)

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"/accounts/login/?next={url}",
                    fetch_redirect_response=False,
                )


class ApplicationNavigationTests(StaffTestCase):
    def test_applications_link_is_current_on_every_application_page(self):
        application = make_application()
        self.client.force_login(self.staff[0])
        marked = f'href="{LIST_URL}" class="menu-active" aria-current="page"'
        for url in (LIST_URL, CREATE_URL, detail_url(application)):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), marked)
