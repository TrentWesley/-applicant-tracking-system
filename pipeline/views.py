from typing import NamedTuple

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import patch_vary_headers
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from candidates.models import Candidate
from core.views import StaffPermissionMixin
from pipeline.forms import ApplicationForm, ApplicationNotesForm
from pipeline.models import Application, Stage
from pipeline.services import (
    NoteRequired,
    StageChangeRefused,
    available_moves,
    change_stage,
    create_application,
    reactivation_target,
)


class Feedback(NamedTuple):
    ok: bool
    text: str


def stage_card_context(application, feedback=None, confirm="", focus=""):
    """
    What the stage card and the history table need, on the detail page and after a move.
    `confirm` names a note-requiring action whose inline note form should be open; `focus` names
    one whose link gets keyboard focus (after Cancel). Both are ignored unless that action is
    allowed from the current stage.
    """
    moves = available_moves(application.stage, reactivation_target(application))
    note_moves = {m.action: m for m in moves if m.needs_note}
    return {
        "application": application,
        "moves": moves,
        "confirming": note_moves.get(confirm),
        "focus": focus if focus in note_moves else "",
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

    def get_template_names(self):
        # The note links and Cancel fetch just the card over HTMX (`?confirm=<action>` opens a
        # note form); without HTMX the same links load the whole page.
        if self.request.headers.get("HX-Request"):
            return ["pipeline/_stage_card.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        card = stage_card_context(
            self.object,
            confirm=self.request.GET.get("confirm", ""),
            focus=self.request.GET.get("focus", ""),
        )
        notes_form = ApplicationNotesForm(instance=self.object)
        return super().get_context_data(**card, notes_form=notes_form, **kwargs)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # The URL serves both the page and the card, so caches must keep them apart.
        patch_vary_headers(response, ["HX-Request"])
        return response


class ApplicationTransitionView(StaffPermissionMixin, View):
    """
    POST action + expected_stage (hidden fields on the stage card), plus a note for Reject,
    Withdraw and Reactivate. With HTMX the refreshed card comes back, plus the history table out
    of band; without it, the detail page reloads. A missing note keeps the note form open.
    """

    permission_required = "pipeline.change_application"
    http_method_names = ["post"]

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        action = request.POST.get("action", "")
        confirm = ""
        try:
            move = change_stage(
                application=application,
                action=action,
                expected_stage=request.POST.get("expected_stage", ""),
                changed_by=request.user,
                note=request.POST.get("note", ""),
            )
        except StageChangeRefused as refusal:
            feedback = Feedback(ok=False, text=str(refusal))
            if isinstance(refusal, NoteRequired):
                confirm = action
            # A stale refusal means another request moved it; show where it is now.
            application.refresh_from_db()
        else:
            moved = f"{move.get_from_stage_display()} to {move.get_to_stage_display()}"
            feedback = Feedback(ok=True, text=f"Moved from {moved}.")

        if request.headers.get("HX-Request"):
            context = stage_card_context(application, feedback, confirm)
            return render(request, "pipeline/_transition_response.html", context)
        level = messages.SUCCESS if feedback.ok else messages.ERROR
        messages.add_message(request, level, feedback.text)
        if confirm:
            return redirect(f"{application.get_absolute_url()}?confirm={confirm}")
        return redirect(application)


class ApplicationNotesView(StaffPermissionMixin, UpdateView):
    """
    POST the application's general notes. Only the notes column is written (the form saves with
    update_fields), so the stage, its time and the history are never touched, even by a request
    that loaded the application before another request moved it. With HTMX the notes card comes
    back; without it, the detail page reloads.
    """

    permission_required = "pipeline.change_application"
    http_method_names = ["post"]
    model = Application
    form_class = ApplicationNotesForm

    def form_valid(self, form):
        self.object = form.save()
        return self.respond(form, Feedback(ok=True, text="Notes saved."))

    def form_invalid(self, form):
        return self.respond(form, Feedback(ok=False, text="The notes couldn't be saved."))

    def respond(self, form, feedback):
        if self.request.headers.get("HX-Request"):
            context = {"application": self.object, "notes_form": form, "feedback": feedback}
            return render(self.request, "pipeline/_notes_card.html", context)
        level = messages.SUCCESS if feedback.ok else messages.ERROR
        messages.add_message(self.request, level, feedback.text)
        return redirect(self.object)
