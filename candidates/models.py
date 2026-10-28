from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse

DUPLICATE_EMAIL_MESSAGE = "A candidate with this email already exists."


class Source(models.TextChoices):
    REFERRAL = "referral", "Referral"
    COMPANY_WEBSITE = "company_website", "Company Website"
    JOB_BOARD = "job_board", "Job Board"
    LINKEDIN = "linkedin", "LinkedIn"
    CAREER_FAIR = "career_fair", "Career Fair"
    AGENCY = "agency", "Agency"
    OTHER = "other", "Other"


class Candidate(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    source = models.CharField(max_length=20, choices=Source)
    source_details = models.CharField(
        max_length=255, blank=True, help_text="For example, who referred them or which job board."
    )
    notes = models.TextField(blank=True)
    profile_url = models.URLField(blank=True, verbose_name="LinkedIn or portfolio URL")
    # Null while the candidate is active; set when archived (Phase 8).
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="candidate_email_unique_ignoring_case",
                violation_error_message=DUPLICATE_EMAIL_MESSAGE,
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse("candidates:candidate_detail", args=[self.pk])
