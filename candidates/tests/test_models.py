from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from candidates.models import Candidate, Source
from candidates.tests.utils import make_candidate


class CandidateEmailConstraintTests(TestCase):
    def test_email_differing_only_in_case_is_refused_by_the_database(self):
        make_candidate(email="Ann.Lee@Example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_candidate(email="ann.lee@example.COM")
        self.assertEqual(Candidate.objects.count(), 1)

    def test_identical_email_is_refused_by_the_database(self):
        make_candidate(email="ann.lee@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_candidate(email="ann.lee@example.com")

    def test_different_emails_are_allowed(self):
        make_candidate(email="ann.lee@example.com")
        make_candidate(email="ann.lee2@example.com")
        self.assertEqual(Candidate.objects.count(), 2)

    def test_model_validation_reports_the_duplicate(self):
        make_candidate(email="ann.lee@example.com")
        duplicate = Candidate(
            first_name="A", last_name="L", email="ANN.LEE@example.com", source=Source.OTHER
        )
        with self.assertRaisesMessage(
            ValidationError, "A candidate with this email already exists."
        ):
            duplicate.full_clean()


class CandidateFieldTests(TestCase):
    def test_source_choices_are_the_fixed_list(self):
        self.assertEqual(
            Source.labels,
            [
                "Referral",
                "Company Website",
                "Job Board",
                "LinkedIn",
                "Career Fair",
                "Agency",
                "Other",
            ],
        )

    def test_only_names_email_and_source_are_required(self):
        candidate = Candidate(
            first_name="Ann", last_name="Lee", email="ann@example.com", source=Source.LINKEDIN
        )
        candidate.full_clean()  # phone, source details, notes, profile URL may be blank

    def test_required_fields_are_enforced_by_model_validation(self):
        with self.assertRaises(ValidationError) as caught:
            Candidate().full_clean()
        self.assertEqual(
            set(caught.exception.message_dict),
            {"first_name", "last_name", "email", "source"},
        )

    def test_invalid_source_and_url_are_refused(self):
        candidate = Candidate(
            first_name="Ann",
            last_name="Lee",
            email="ann@example.com",
            source="newspaper",
            profile_url="not a url",
        )
        with self.assertRaises(ValidationError) as caught:
            candidate.full_clean()
        self.assertEqual(set(caught.exception.message_dict), {"source", "profile_url"})

    def test_new_candidate_is_active_with_timestamps(self):
        candidate = make_candidate()
        self.assertIsNone(candidate.archived_at)
        self.assertIsNotNone(candidate.created_at)
        self.assertIsNotNone(candidate.updated_at)

    def test_string_and_url(self):
        candidate = make_candidate(first_name="Ann", last_name="Lee")
        self.assertEqual(str(candidate), "Ann Lee")
        self.assertEqual(candidate.get_absolute_url(), f"/candidates/{candidate.pk}/")

    def test_ordered_by_last_then_first_name(self):
        make_candidate(email="c@example.com", first_name="Cy", last_name="Zane")
        make_candidate(email="b@example.com", first_name="Bo", last_name="Adams")
        make_candidate(email="a@example.com", first_name="Al", last_name="Adams")
        self.assertEqual(
            [str(c) for c in Candidate.objects.all()], ["Al Adams", "Bo Adams", "Cy Zane"]
        )
