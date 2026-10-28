from django import forms

from core.forms import CheckboxSelectMultiple, DaisyUIFormMixin
from jobs.models import DUPLICATE_SKILL_MESSAGE, JobOpening, Skill


class SkillForm(DaisyUIFormMixin, forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name"]

    def clean_name(self):
        # The database constraint is the final guard; this puts the message on the name field.
        name = self.cleaned_data["name"]
        duplicates = Skill.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(DUPLICATE_SKILL_MESSAGE, code="duplicate_name")
        return name


class JobOpeningForm(DaisyUIFormMixin, forms.ModelForm):
    """Status is deliberately absent: it changes only through Close and Reopen."""

    class Meta:
        model = JobOpening
        fields = [
            "title",
            "department",
            "location",
            "employment_type",
            "work_mode",
            "skills",
            "description",
        ]
        widgets = {
            "skills": CheckboxSelectMultiple,
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        help_texts = {"skills": "Choose the skills this job requires. Admins manage the list."}


class JobFilterForm(DaisyUIFormMixin, forms.Form):
    """The ?skill=<pk> filter on the job list."""

    skill = forms.ModelChoiceField(Skill.objects.all(), required=False, empty_label="All skills")
