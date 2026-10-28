from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from candidates.forms import CandidateForm
from candidates.models import Candidate
from core.views import StaffPermissionMixin


class CandidateListView(StaffPermissionMixin, ListView):
    permission_required = "candidates.view_candidate"
    queryset = Candidate.objects.filter(archived_at__isnull=True)
    context_object_name = "candidates"


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
