from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.functional import cached_property
from django.views.generic import CreateView, DetailView, ListView

from candidates.models import Candidate
from core.views import StaffPermissionMixin
from pipeline.forms import ApplicationForm
from pipeline.models import Application, Stage
from pipeline.services import StageChangeRefused, create_application


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
        history = self.object.stage_changes.select_related("changed_by")
        return super().get_context_data(history=history, **kwargs)
