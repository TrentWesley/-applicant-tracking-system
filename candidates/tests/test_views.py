from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import DUPLICATE_EMAIL_MESSAGE, Candidate, Source
from candidates.tests.utils import make_candidate
from core.tests.utils import make_admin, make_recruiter, make_user

LIST_URL = reverse("candidates:candidate_list")
CREATE_URL = reverse("candidates:candidate_create")

VALID = {
    "first_name": "Maria",
    "last_name": "Rivera",
    "email": "maria.rivera@example.com",
    "source": Source.JOB_BOARD,
    "source_details": "Indeed",
}


def detail_url(candidate):
    return reverse("candidates:candidate_detail", args=[candidate.pk])


def edit_url(candidate):
    return reverse("candidates:candidate_update", args=[candidate.pk])


def make_viewer():
    """A staff user who may only view candidates."""
    user = make_user("viewer")
    user.user_permissions.add(Permission.objects.get(codename="view_candidate"))
    return user


class StaffTestCase(TestCase):
    def setUp(self):
        self.staff = [make_recruiter(), make_admin()]


class CandidateListTests(StaffTestCase):
    def test_recruiter_and_admin_see_active_candidates_linked_to_detail(self):
        candidate = make_candidate(first_name="Ann", last_name="Lee")
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(LIST_URL)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "candidates/candidate_list.html")
                self.assertContains(response, f'href="{detail_url(candidate)}"')
                self.assertContains(response, "Ann Lee")
                self.assertContains(response, "Referral")

    def test_list_excludes_archived_candidates(self):
        make_candidate(email="active@example.com", first_name="Active")
        make_candidate(email="gone@example.com", first_name="Archived", archived_at=timezone.now())
        self.client.force_login(self.staff[0])
        response = self.client.get(LIST_URL)
        self.assertEqual([c.first_name for c in response.context["candidates"]], ["Active"])
        self.assertNotContains(response, "Archived Lee")

    def test_empty_list_says_so(self):
        self.client.force_login(self.staff[0])
        self.assertContains(self.client.get(LIST_URL), "No candidates yet.")

    def test_add_button_shown_to_users_who_can_add(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(LIST_URL), f'href="{CREATE_URL}"')

    def test_add_button_hidden_from_view_only_users(self):
        self.client.force_login(make_viewer())
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{CREATE_URL}"')


class CandidateDetailTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(
            first_name="Maria",
            last_name="Rivera",
            email="maria.rivera@example.com",
            phone="806-555-0100",
            source=Source.JOB_BOARD,
            source_details="Indeed posting",
            notes="Strong SQL background.",
            profile_url="https://www.linkedin.com/in/maria-rivera",
        )

    def test_detail_shows_every_field(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url(self.candidate))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Maria Rivera</h1>")
                self.assertContains(response, 'href="mailto:maria.rivera@example.com"')
                self.assertContains(response, "806-555-0100")
                self.assertContains(response, "Job Board")
                self.assertContains(response, "Indeed posting")
                self.assertContains(response, "Strong SQL background.")
                self.assertContains(response, 'href="https://www.linkedin.com/in/maria-rivera"')

    def test_edit_button_shown_to_users_who_can_change(self):
        self.client.force_login(self.staff[0])
        self.assertContains(
            self.client.get(detail_url(self.candidate)), f'href="{edit_url(self.candidate)}"'
        )

    def test_edit_button_hidden_from_view_only_users(self):
        self.client.force_login(make_viewer())
        response = self.client.get(detail_url(self.candidate))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{edit_url(self.candidate)}"')

    def test_unknown_candidate_is_404(self):
        self.client.force_login(self.staff[0])
        self.assertEqual(self.client.get("/candidates/999999/").status_code, 404)


class CandidateCreateTests(StaffTestCase):
    def test_form_page_renders_labelled_fields(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add candidate</h1>")
        for field in ("first_name", "last_name", "email", "phone", "source", "source_details"):
            self.assertContains(response, f'<label for="id_{field}"')
        self.assertContains(response, "LinkedIn or portfolio URL")
        self.assertNotContains(response, "archived_at")

    def test_recruiter_and_admin_create_and_land_on_detail(self):
        for index, user in enumerate(self.staff):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                email = f"maria{index}@example.com"
                response = self.client.post(CREATE_URL, VALID | {"email": email}, follow=True)
                candidate = Candidate.objects.get(email=email)
                self.assertRedirects(response, detail_url(candidate))
                self.assertContains(response, "Candidate Maria Rivera added.")
                self.assertEqual(candidate.source, Source.JOB_BOARD)
                self.assertEqual(candidate.source_details, "Indeed")

    def test_duplicate_email_in_another_case_is_refused_with_message(self):
        make_candidate(email="Maria.Rivera@example.com")
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, VALID | {"email": "MARIA.RIVERA@EXAMPLE.COM"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_EMAIL_MESSAGE)
        self.assertEqual(Candidate.objects.count(), 1)

    def test_field_errors_are_linked_to_their_inputs_for_screen_readers(self):
        make_candidate(email="maria.rivera@example.com")
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, VALID)
        self.assertContains(response, 'aria-invalid="true" aria-describedby="id_email_error"')
        self.assertContains(response, '<div id="id_email_error"')

    def test_missing_required_field_is_refused(self):
        self.client.force_login(self.staff[0])
        response = self.client.post(CREATE_URL, VALID | {"source": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(Candidate.objects.exists())


class CandidateUpdateTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(email="maria.rivera@example.com", first_name="Maria")

    def test_form_is_prefilled(self):
        self.client.force_login(self.staff[0])
        response = self.client.get(edit_url(self.candidate))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Maria Lee</h1>")
        self.assertContains(response, 'value="maria.rivera@example.com"')

    def test_recruiter_and_admin_edit_and_land_on_detail(self):
        for user in self.staff:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                data = VALID | {"first_name": f"M-{user.username}", "phone": "555"}
                response = self.client.post(edit_url(self.candidate), data, follow=True)
                self.assertRedirects(response, detail_url(self.candidate))
                self.assertContains(response, "changes saved")
                self.candidate.refresh_from_db()
                self.assertEqual(self.candidate.first_name, f"M-{user.username}")
                self.assertEqual(self.candidate.phone, "555")

    def test_edit_applies_the_same_validation_as_create(self):
        make_candidate(email="sam.o@example.com")
        self.client.force_login(self.staff[0])
        cases = {
            "duplicate email": {"email": "SAM.O@example.com"},
            "missing last name": {"last_name": ""},
            "invalid URL": {"profile_url": "not a url"},
            "invalid source": {"source": "newspaper"},
        }
        for case, change in cases.items():
            with self.subTest(case=case):
                response = self.client.post(edit_url(self.candidate), VALID | change)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.candidate.refresh_from_db()
                self.assertEqual(self.candidate.email, "maria.rivera@example.com")
                self.assertEqual(self.candidate.last_name, "Lee")

    def test_duplicate_message_shown_on_edit(self):
        make_candidate(email="sam.o@example.com")
        self.client.force_login(self.staff[0])
        response = self.client.post(
            edit_url(self.candidate), VALID | {"email": "Sam.O@example.com"}
        )
        self.assertContains(response, DUPLICATE_EMAIL_MESSAGE)


class CandidatePermissionTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate(email="ann@example.com")

    def test_user_without_permissions_gets_403_everywhere(self):
        self.client.force_login(make_user("nobody"))
        for url in (LIST_URL, CREATE_URL, detail_url(self.candidate), edit_url(self.candidate)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_forbidden_create_writes_nothing(self):
        self.client.force_login(make_user("nobody"))
        response = self.client.post(CREATE_URL, VALID)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Candidate.objects.count(), 1)

    def test_forbidden_edit_changes_nothing(self):
        self.client.force_login(make_viewer())
        response = self.client.post(edit_url(self.candidate), VALID)
        self.assertEqual(response.status_code, 403)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.email, "ann@example.com")

    def test_view_only_user_can_view_but_not_add_or_edit(self):
        self.client.force_login(make_viewer())
        self.assertEqual(self.client.get(LIST_URL).status_code, 200)
        self.assertEqual(self.client.get(detail_url(self.candidate)).status_code, 200)
        self.assertEqual(self.client.get(CREATE_URL).status_code, 403)
        self.assertEqual(self.client.get(edit_url(self.candidate)).status_code, 403)

    def test_anonymous_users_are_redirected_to_login(self):
        for url in (LIST_URL, CREATE_URL, detail_url(self.candidate), edit_url(self.candidate)):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"/accounts/login/?next={url}", fetch_redirect_response=False
                )


class CandidateNavigationTests(StaffTestCase):
    def test_candidates_nav_link_is_current_on_every_candidate_page(self):
        candidate = make_candidate()
        self.client.force_login(self.staff[0])
        marked = f'href="{LIST_URL}" class="menu-active" aria-current="page"'
        for url in (LIST_URL, CREATE_URL, detail_url(candidate), edit_url(candidate)):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), marked)
