from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from core.forms import DaisyUIFormMixin
from core.roles import ADMIN, RECRUITER
from staff.services import set_role

DUPLICATE_EMAIL_MESSAGE = "A staff account with this email already exists."


class StaffCreateForm(DaisyUIFormMixin, UserCreationForm):
    """
    Django's user creation form (case-insensitive unique username, password and confirmation
    checked by AUTH_PASSWORD_VALIDATORS) plus name, email and a role. Superuser and staff flags
    aren't fields, so they can't be posted.
    """

    role = forms.ChoiceField(choices=[(RECRUITER, RECRUITER), (ADMIN, ADMIN)], initial=RECRUITER)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Names appear on every history entry, and email identifies the account.
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(DUPLICATE_EMAIL_MESSAGE, code="duplicate_email")
        return email

    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=commit)
            if commit:
                set_role(user, self.cleaned_data["role"])
        return user
