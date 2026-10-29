from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from candidates.forms import CandidateForm
from candidates.models import Candidate
from candidates.services import (
    CandidateStatusRefused,
    archive_candidate,
    delete_candidate,
    deletion_blocker,
    restore_candidate,
)
from core.views import AdminDeleteView, StaffPermissionMixin


class CandidateListView(StaffPermissionMixin, ListView):
    permission_required = "candidates.view_candidate"
    queryset = Candidate.objects.filter(archived_at__isnull=True)
    context_object_name = "candidates"


class ArchivedCandidateListView(CandidateListView):
    queryset = Candidate.objects.filter(archived_at__isnull=False)
    extra_context = {"show_archived": True}


class CandidateDetailView(StaffPermissionMixin, DetailView):
    permission_required = "candidates.view_candidate"
    model = Candidate

    def get_context_data(self, **kwargs):
        applications = self.object.applications.select_related("job_opening")
        return super().get_context_data(applications=applications, **kwargs)


class CandidateCreateView(StaffPermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "candidates.add_candidate"
    model = Candidate
    form_class = CandidateForm
    success_message = "Candidate %(first_name)s %(last_name)s added."


class CandidateUpdateView(StaffPermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "candidates.change_candidate"
    model = Candidate
    form_class = CandidateForm
    success_message = "Candidate %(first_name)s %(last_name)s: changes saved."


class CandidateStatusActionView(StaffPermissionMixin, View):
    """POST-only Archive or Restore; the detail page reloads with the outcome."""

    permission_required = "candidates.change_candidate"
    http_method_names = ["post"]
    change = None  # archive_candidate or restore_candidate
    success_message = ""

    def post(self, request, pk):
        candidate = get_object_or_404(Candidate, pk=pk)
        try:
            self.change(candidate)
        except CandidateStatusRefused as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(request, self.success_message.format(candidate=candidate))
        return redirect(candidate)


class CandidateArchiveView(CandidateStatusActionView):
    change = staticmethod(archive_candidate)
    success_message = "{candidate} archived."


class CandidateRestoreView(CandidateStatusActionView):
    change = staticmethod(restore_candidate)
    success_message = "{candidate} restored."


class CandidateDeleteView(AdminDeleteView):
    permission_required = "candidates.delete_candidate"
    model = Candidate
    delete_record = staticmethod(delete_candidate)
    blocker = staticmethod(deletion_blocker)
    kind = "candidate"
    warning = "This permanently deletes the candidate and their details. It can't be undone."
    success_url = reverse_lazy("candidates:candidate_list")
