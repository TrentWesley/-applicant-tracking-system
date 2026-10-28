from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from candidates.forms import CandidateForm
from candidates.models import Candidate


class CandidatePermissionMixin(PermissionRequiredMixin):
    # Login is enforced by LoginRequiredMiddleware; a signed-in user without the permission
    # gets 403 instead of a login redirect.
    raise_exception = True


class CandidateListView(CandidatePermissionMixin, ListView):
    permission_required = "candidates.view_candidate"
    queryset = Candidate.objects.filter(archived_at__isnull=True)
    context_object_name = "candidates"


class CandidateDetailView(CandidatePermissionMixin, DetailView):
    permission_required = "candidates.view_candidate"
    model = Candidate


class CandidateCreateView(CandidatePermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "candidates.add_candidate"
    model = Candidate
    form_class = CandidateForm
    success_message = "Candidate %(first_name)s %(last_name)s added."


class CandidateUpdateView(CandidatePermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "candidates.change_candidate"
    model = Candidate
    form_class = CandidateForm
    success_message = "Candidate %(first_name)s %(last_name)s: changes saved."
