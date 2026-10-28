from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user
from jobs.tests.utils import make_job
from pipeline.models import Stage
from pipeline.tests.utils import make_application

CREATE_URL = reverse("pipeline:application_create")


class NewApplicationEntryPointTests(TestCase):
    """AC33: both entry points open the same creation form."""

    def setUp(self):
        self.staff = [make_recruiter(), make_admin()]
        self.candidate = make_candidate(first_name="Ann", last_name="Lee")

    def test_list_and_candidate_page_link_to_the_same_form(self):
        candidate_link = f'href="{CREATE_URL}?candidate={self.candidate.pk}"'
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                list_page = self.client.get(reverse("pipeline:application_list"))
                self.assertContains(list_page, f'href="{CREATE_URL}"')
                self.assertContains(
                    self.client.get(self.candidate.get_absolute_url()), candidate_link
                )

    def test_archived_candidate_page_has_no_new_application_button(self):
        self.candidate.archived_at = timezone.now()
        self.candidate.save()
        self.client.force_login(self.staff[0])
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, CREATE_URL)
        self.assertContains(response, "Archived candidates can't get new applications.")

    def test_button_hidden_from_users_who_cannot_add_applications(self):
        user = make_user("viewer")
        user.user_permissions.add(Permission.objects.get(codename="view_candidate"))
        self.client.force_login(user)
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, CREATE_URL)


class CandidateApplicationsSectionTests(TestCase):
    def setUp(self):
        self.client.force_login(make_recruiter())
        self.candidate = make_candidate()

    def test_candidate_page_lists_their_applications_with_stage_badges(self):
        analyst = make_application(self.candidate, make_job("Data Analyst"))
        engineer = make_application(
            self.candidate, make_job("Engineer"), created_by=make_admin(), stage=Stage.OFFER
        )
        make_application(make_candidate("other@example.com"), make_job("Unrelated Role"))
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertTemplateUsed(response, "core/_stage_badge.html")
        self.assertContains(response, f'href="{analyst.get_absolute_url()}"')
        self.assertContains(response, f'href="{engineer.get_absolute_url()}"')
        self.assertContains(response, ">Applied</span>")
        self.assertContains(response, ">Offer</span>")
        self.assertNotContains(response, "Unrelated Role")

    def test_candidate_without_applications_says_so(self):
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertContains(response, "No applications yet.")
