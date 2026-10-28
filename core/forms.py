from django import forms
from django.contrib.auth.forms import AuthenticationForm


class DaisyUIFormMixin:
    """Give every widget the matching DaisyUI class (input, select, textarea, checkbox)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "checkbox"
            elif isinstance(widget, forms.Select):
                css = "select w-full"
            elif isinstance(widget, forms.Textarea):
                css = "textarea w-full"
            else:
                css = "input w-full"
            widget.attrs["class"] = css


class LoginForm(DaisyUIFormMixin, AuthenticationForm):
    """Django's login form with DaisyUI input styling."""
