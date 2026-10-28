from typing import NamedTuple

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from candidates.models import Candidate
from core.views import StaffPermissionMixin
from pipeline.forms import ApplicationForm
from pipeline.models import Application, Stage
from pipeline.services import (
    StageChangeRefused,
    available_moves,
    change_stage,
    create_application,
)


class Feedback(NamedTuple):
    ok: bool
    text: str


def stage_card_context(application, feedback=None):
    """What the stage card and the history table need, on the detail page and after a move."""
    return {
        "application": application,
        "moves": available_moves(application.stage),
        "history": application.stage_changes.select_related("changed_by"),
        "feedback": feedback,
    }


class ApplicationListView(StaffPermissionMixin, ListView):
    permission_required = "pipeline.view_application"
    context_object_name = "applications"
    template_name = "pipeline/application_list.html"

    def get_queryset(self):
        applications = Application.objects.select_related("candidate", "job_opening")
        # ?stage=<value> covers applications on open and closed jobs; unknown values are ignored.
        value = self.request.GET.get("stage")
        self.stage = Stage(value) if value in Stage.values else None
        return applications.filter(stage=self.stage) if self.stage else applications

    def get_context_data(self, **kwargs):
        return super().get_context_data(stage=self.stage, stages=list(Stage), **kwargs)


class ApplicationCreateView(StaffPermissionMixin, CreateView):
    """
    The one creation form, opened from the Applications list or (with ?candidate=<pk>) from a
    candidate's page. Saving goes through the stage-change service.
    """

    permission_required = "pipeline.add_application"
    form_class = ApplicationForm
    template_name = "pipeline/application_form.html"

    @cached_property
    def preselected_candidate(self):
        # Only an active candidate is preselected; the form refuses anyone else on submit.
        pk = self.request.GET.get("candidate", "")
        if not pk.isdigit():
            return None
        return Candidate.objects.filter(pk=pk, archived_at__isnull=True).first()

    def get_initial(self):
        return super().get_initial() | {"candidate": self.preselected_candidate}

    def get_context_data(self, **kwargs):
        return super().get_context_data(from_candidate=self.preselected_candidate, **kwargs)

    def form_valid(self, form):
        try:
            self.object = create_application(created_by=self.request.user, **form.cleaned_data)
        except StageChangeRefused as refusal:
            form.add_error(None, str(refusal))
            return self.form_invalid(form)
        messages.success(self.request, f"Application created: {self.object}.")
        return HttpResponseRedirect(self.object.get_absolute_url())


class ApplicationDetailView(StaffPermissionMixin, DetailView):
    permission_required = "pipeline.view_application"
    queryset = Application.objects.select_related("candidate", "job_opening", "created_by")
    context_object_name = "application"
    template_name = "pipeline/application_detail.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**stage_card_context(self.object), **kwargs)


class ApplicationTransitionView(StaffPermissionMixin, View):
    """
    POST action + expected_stage (hidden fields on the stage card). With HTMX the refreshed card
    comes back, plus the history table out of band; without it, the detail page reloads.
    """

    permission_required = "pipeline.change_application"
    http_method_names = ["post"]

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        try:
            move = change_stage(
                application=application,
                action=request.POST.get("action", ""),
                expected_stage=request.POST.get("expected_stage", ""),
                changed_by=request.user,
                note=request.POST.get("note", ""),
            )
        except StageChangeRefused as refusal:
            feedback = Feedback(ok=False, text=str(refusal))
            # A stale refusal means another request moved it; show where it is now.
            application.refresh_from_db()
        else:
            moved = f"{move.get_from_stage_display()} to {move.get_to_stage_display()}"
            feedback = Feedback(ok=True, text=f"Moved from {moved}.")

        if request.headers.get("HX-Request"):
            context = stage_card_context(application, feedback)
            return render(request, "pipeline/_transition_response.html", context)
        level = messages.SUCCESS if feedback.ok else messages.ERROR
        messages.add_message(request, level, feedback.text)
        return redirect(application)
