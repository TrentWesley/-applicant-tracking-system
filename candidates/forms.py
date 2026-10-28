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

    def save(self, commit=True):
        # An edit writes only its own fields. Saving every column from the copy this request
        # loaded would undo an Archive or Restore committed in between.
        candidate = super().save(commit=False)
        if commit:
            if candidate._state.adding:
                candidate.save()
            else:
                candidate.save(update_fields=[*self._meta.fields, "updated_at"])
            self.save_m2m()
        return candidate

    def clean_email(self):
        # The database constraint is the final guard; this puts the message on the email field.
        email = self.cleaned_data["email"]
        duplicates = Candidate.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(DUPLICATE_EMAIL_MESSAGE, code="duplicate_email")
        return email
