from django import forms

from candidates.models import DUPLICATE_EMAIL_MESSAGE, Candidate
from core.forms import DaisyUIFormMixin


class CandidateForm(DaisyUIFormMixin, forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "source",
            "source_details",
            "profile_url",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def clean_email(self):
        # The database constraint is the final guard; this puts the message on the email field.
        email = self.cleaned_data["email"]
        duplicates = Candidate.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(DUPLICATE_EMAIL_MESSAGE, code="duplicate_email")
        return email
