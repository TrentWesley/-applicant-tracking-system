from django import forms

from candidates.models import Candidate
from core.forms import DaisyUIFormMixin, SaveOnlyFormFieldsMixin
from jobs.models import JobOpening, JobStatus
from pipeline.models import Application

CLOSED_JOB_CHOICE_MESSAGE = "Choose an open job. Closed jobs don't accept new applications."
ARCHIVED_CANDIDATE_CHOICE_MESSAGE = (
    "Choose an active candidate. Archived candidates can't get new applications."
)


class ApplicationForm(DaisyUIFormMixin, forms.ModelForm):
    """
    Offers only Open jobs and non-archived candidates. The view saves through the stage-change
    service, which checks every guard again inside its transaction.
    """

    class Meta:
        model = Application
        fields = ["candidate", "job_opening", "notes"]
        labels = {"job_opening": "Job opening"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"notes": "General notes about this application. Optional."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        candidate = self.fields["candidate"]
        candidate.queryset = Candidate.objects.filter(archived_at__isnull=True)
        candidate.label_from_instance = lambda c: f"{c} ({c.email})"
        candidate.error_messages["invalid_choice"] = ARCHIVED_CANDIDATE_CHOICE_MESSAGE

        job = self.fields["job_opening"]
        job.queryset = JobOpening.objects.filter(status=JobStatus.OPEN)
        job.label_from_instance = lambda j: f"{j} ({j.department})" if j.department else str(j)
        job.error_messages["invalid_choice"] = CLOSED_JOB_CHOICE_MESSAGE


class ApplicationNotesForm(SaveOnlyFormFieldsMixin, DaisyUIFormMixin, forms.ModelForm):
    """General notes only; saving never touches the stage (see SaveOnlyFormFieldsMixin)."""

    class Meta:
        model = Application
        fields = ["notes"]
        labels = {"notes": "General notes"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"notes": "Saving notes doesn't change the stage or its history."}
