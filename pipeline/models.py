from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from jobs.models import JobOpening

DUPLICATE_APPLICATION_MESSAGE = "This candidate already has an application for this job."


class Stage(models.TextChoices):
    APPLIED = "applied", "Applied"
    SCREENING = "screening", "Screening"
    INTERVIEW = "interview", "Interview"
    FINAL_REVIEW = "final_review", "Final Review"
    OFFER = "offer", "Offer"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"

    @property
    def is_active(self):
        return self in ACTIVE_STAGES


ACTIVE_STAGES = (Stage.APPLIED, Stage.SCREENING, Stage.INTERVIEW, Stage.FINAL_REVIEW, Stage.OFFER)
TERMINAL_STAGES = (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN)


class Application(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="applications")
    job_opening = models.ForeignKey(
        JobOpening, on_delete=models.PROTECT, related_name="applications"
    )
    # Stage fields change only through the stage-change service, never a form.
    stage = models.CharField(max_length=20, choices=Stage, default=Stage.APPLIED, editable=False)
    stage_changed_at = models.DateTimeField(editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="applications_created",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-stage_changed_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job_opening"],
                name="application_unique_candidate_job",
                violation_error_message=DUPLICATE_APPLICATION_MESSAGE,
            ),
        ]

    def __str__(self):
        return f"{self.candidate} for {self.job_opening}"

    def get_absolute_url(self):
        return reverse("pipeline:application_detail", args=[self.pk])


class HistoryIsImmutable(Exception):
    """Raised when code tries to change or remove a StageChange row."""

    def __init__(self):
        super().__init__("Stage history is append-only: entries can't be changed or deleted.")


class StageChangeQuerySet(models.QuerySet):
    # Deleting an Application still removes its history: Django's cascade deletes the rows
    # directly, without going through this method.
    def update(self, **kwargs):
        raise HistoryIsImmutable

    def bulk_update(self, objs, fields, batch_size=None):
        # bulk_update doesn't call update(), so it needs its own refusal.
        raise HistoryIsImmutable

    def delete(self):
        raise HistoryIsImmutable


class StageChange(models.Model):
    """
    One entry in an application's append-only stage history, written only by the stage-change
    service. Updates are also refused by a database trigger (migration 0002).
    """

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="stage_changes"
    )
    # Null for the creation entry, which has no previous stage.
    from_stage = models.CharField(max_length=20, choices=Stage, null=True, blank=True)  # noqa: DJ001
    to_stage = models.CharField(max_length=20, choices=Stage)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stage_changes"
    )
    changed_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    objects = StageChangeQuerySet.as_manager()

    class Meta:
        ordering = ["changed_at", "pk"]
        default_permissions = ()  # no screens create, edit or delete history

    def __str__(self):
        return f"{self.application}: {self.from_stage or 'new'} → {self.to_stage}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise HistoryIsImmutable
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise HistoryIsImmutable
