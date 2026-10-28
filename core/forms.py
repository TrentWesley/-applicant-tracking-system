from django import forms
from django.contrib.auth.forms import AuthenticationForm


class DaisyUIFormMixin:
    """Give every widget the matching DaisyUI class (input, select, textarea, checkbox)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = "checkbox"
            elif isinstance(widget, forms.Select):
                css = "select w-full"
            elif isinstance(widget, forms.Textarea):
                css = "textarea w-full"
            else:
                css = "input w-full"
            widget.attrs["class"] = css


class CheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """
    Django copies widget attrs onto the wrapping <div> as well as each checkbox, so the DaisyUI
    class would draw the whole list as one box. Keep the class on the checkboxes only.
    """

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].pop("class", None)
        return context


class LoginForm(DaisyUIFormMixin, AuthenticationForm):
    """Django's login form with DaisyUI input styling."""
