from django.test import TestCase

from candidates.forms import CandidateForm
from candidates.models import DUPLICATE_EMAIL_MESSAGE, Source
from candidates.tests.utils import make_candidate

VALID = {
    "first_name": "Maria",
    "last_name": "Rivera",
    "email": "maria.rivera@example.com",
    "source": Source.JOB_BOARD,
}


class CandidateFormValidationTests(TestCase):
    def test_required_fields_only_is_valid(self):
        form = CandidateForm(data=VALID)
        self.assertTrue(form.is_valid(), form.errors)

    def test_all_fields_filled_is_valid(self):
        data = VALID | {
            "phone": "+1 806 555 0100",
            "source_details": "Indeed posting #42",
            "notes": "Strong SQL background.",
            "profile_url": "https://www.linkedin.com/in/maria-rivera",
        }
        form = CandidateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_each_required_field_is_required(self):
        for field in ("first_name", "last_name", "email", "source"):
            with self.subTest(field=field):
                form = CandidateForm(data=VALID | {field: ""})
                self.assertFalse(form.is_valid())
                self.assertEqual(list(form.errors), [field])

    def test_optional_fields_may_be_blank(self):
        data = VALID | {"phone": "", "source_details": "", "notes": "", "profile_url": ""}
        self.assertTrue(CandidateForm(data=data).is_valid())

    def test_invalid_url_is_refused(self):
        form = CandidateForm(data=VALID | {"profile_url": "not a url"})
        self.assertFalse(form.is_valid())
        self.assertIn("profile_url", form.errors)

    def test_invalid_email_is_refused(self):
        form = CandidateForm(data=VALID | {"email": "maria-at-example"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_source_outside_the_fixed_list_is_refused(self):
        form = CandidateForm(data=VALID | {"source": "newspaper"})
        self.assertFalse(form.is_valid())
        self.assertIn("source", form.errors)

    def test_source_offers_exactly_the_fixed_list(self):
        choices = [label for value, label in CandidateForm().fields["source"].choices if value]
        self.assertEqual(choices, Source.labels)

    def test_archive_state_is_not_editable(self):
        self.assertNotIn("archived_at", CandidateForm().fields)
        form = CandidateForm(data=VALID | {"archived_at": "2026-01-01 00:00"})
        candidate = form.save()
        self.assertIsNone(candidate.archived_at)


class CandidateFormDuplicateEmailTests(TestCase):
    def setUp(self):
        self.existing = make_candidate(email="Maria.Rivera@Example.com")

    def test_duplicate_email_in_another_case_is_refused_with_message(self):
        form = CandidateForm(data=VALID | {"email": "maria.rivera@example.COM"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"email": [DUPLICATE_EMAIL_MESSAGE]})

    def test_identical_duplicate_email_is_refused(self):
        form = CandidateForm(data=VALID | {"email": "Maria.Rivera@Example.com"})
        self.assertEqual(form.errors, {"email": [DUPLICATE_EMAIL_MESSAGE]})

    def test_duplicate_with_surrounding_spaces_is_refused(self):
        form = CandidateForm(data=VALID | {"email": "  maria.rivera@example.com "})
        self.assertEqual(form.errors, {"email": [DUPLICATE_EMAIL_MESSAGE]})

    def test_editing_without_changing_email_is_allowed(self):
        data = VALID | {"email": self.existing.email, "first_name": "Mariana"}
        form = CandidateForm(data=data, instance=self.existing)
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_own_email_to_another_case_is_allowed(self):
        form = CandidateForm(
            data=VALID | {"email": "maria.rivera@example.com"}, instance=self.existing
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_to_another_candidates_email_is_refused(self):
        other = make_candidate(email="sam.o@example.com")
        form = CandidateForm(data=VALID | {"email": "MARIA.RIVERA@example.com"}, instance=other)
        self.assertEqual(form.errors, {"email": [DUPLICATE_EMAIL_MESSAGE]})


class CandidateFormStylingTests(TestCase):
    def test_widgets_use_daisyui_classes(self):
        fields = CandidateForm().fields
        self.assertEqual(fields["first_name"].widget.attrs["class"], "input w-full")
        self.assertEqual(fields["source"].widget.attrs["class"], "select w-full")
        self.assertEqual(fields["notes"].widget.attrs["class"], "textarea w-full")
