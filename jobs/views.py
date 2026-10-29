from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.views import AdminDeleteView, StaffPermissionMixin
from jobs.forms import JobFilterForm, JobOpeningForm, SkillForm
from jobs.models import JobOpening, Skill
from jobs.services import JobStatusUnchanged, close_job, delete_job, reopen_job
from jobs.services import deletion_blocker as job_deletion_blocker
from pipeline.models import ACTIVE_STAGES, Stage


class JobListView(StaffPermissionMixin, ListView):
    permission_required = "jobs.view_jobopening"
    context_object_name = "jobs"
    template_name = "jobs/job_list.html"

    def get_queryset(self):
        jobs = JobOpening.objects.prefetch_related("skills")
        self.filter_form = JobFilterForm(self.request.GET)
        self.skill = None
        if self.filter_form.is_valid():
            self.skill = self.filter_form.cleaned_data["skill"]
        else:
            # An unknown or malformed ?skill= value is ignored rather than shown as an error.
            self.filter_form = JobFilterForm()
        return jobs.filter(skills=self.skill) if self.skill else jobs

    def get_context_data(self, **kwargs):
        return super().get_context_data(filter_form=self.filter_form, skill=self.skill, **kwargs)


class JobDetailView(StaffPermissionMixin, DetailView):
    permission_required = "jobs.view_jobopening"
    queryset = JobOpening.objects.prefetch_related("skills")
    context_object_name = "job"
    template_name = "jobs/job_detail.html"

    def get_context_data(self, **kwargs):
        # Every application, archived candidates included, and the counts from the same rows
        # (US 25, AC18). A closed job's active count is also the unfinished-work note (US 23).
        applications = list(self.object.applications.select_related("candidate"))
        counts = {
            "total": len(applications),
            "active": sum(a.stage in ACTIVE_STAGES for a in applications),
            "hired": sum(a.stage == Stage.HIRED for a in applications),
        }
        return super().get_context_data(applications=applications, counts=counts, **kwargs)


class JobStatusActionView(StaffPermissionMixin, View):
    """POST-only Close or Reopen; the detail page reloads with the outcome."""

    permission_required = "jobs.change_jobopening"
    http_method_names = ["post"]
    change = None  # close_job or reopen_job
    success_message = ""

    def post(self, request, pk):
        job = get_object_or_404(JobOpening, pk=pk)
        try:
            self.change(job)
        except JobStatusUnchanged as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(request, self.success_message.format(job=job))
        return redirect(job)


class JobCloseView(JobStatusActionView):
    change = staticmethod(close_job)
    success_message = "{job} closed. It no longer accepts new applications."


class JobReopenView(JobStatusActionView):
    change = staticmethod(reopen_job)
    success_message = "{job} reopened. It accepts new applications again."


class JobCreateView(StaffPermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "jobs.add_jobopening"
    model = JobOpening
    form_class = JobOpeningForm
    template_name = "jobs/job_form.html"
    success_message = "Job opening %(title)s added."


class JobUpdateView(StaffPermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "jobs.change_jobopening"
    model = JobOpening
    form_class = JobOpeningForm
    template_name = "jobs/job_form.html"
    success_message = "Job opening %(title)s: changes saved."


class SkillListView(StaffPermissionMixin, ListView):
    # Recruiters may view skills (they appear on jobs), but this management page is Admin-only.
    permission_required = ("jobs.view_skill", "jobs.change_skill")
    # Meta.ordering is dropped from GROUP BY queries, so order explicitly.
    queryset = Skill.objects.annotate(job_count=Count("jobs")).order_by(*Skill._meta.ordering)
    context_object_name = "skills"
    template_name = "jobs/skill_list.html"


class SkillCreateView(StaffPermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "jobs.add_skill"
    model = Skill
    form_class = SkillForm
    template_name = "jobs/skill_form.html"
    success_url = reverse_lazy("jobs:skill_list")
    success_message = "Skill %(name)s added."


class SkillUpdateView(StaffPermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "jobs.change_skill"
    model = Skill
    form_class = SkillForm
    template_name = "jobs/skill_form.html"
    success_url = reverse_lazy("jobs:skill_list")
    success_message = "Skill renamed to %(name)s."


class SkillDeleteView(StaffPermissionMixin, DeleteView):
    permission_required = "jobs.delete_skill"
    model = Skill
    context_object_name = "skill"
    template_name = "jobs/skill_confirm_delete.html"
    success_url = reverse_lazy("jobs:skill_list")

    def get_context_data(self, **kwargs):
        blocking_jobs = self.object.jobs.order_by("title", "pk")
        return super().get_context_data(blocking_jobs=blocking_jobs, **kwargs)

    def form_valid(self, form):
        # Refused while any job, open or closed, uses the skill (AC16). There's no "is it used?"
        # pre-check to race against: JobSkill.skill is PROTECT, and if another request assigns
        # the skill after that lookup, the database foreign key fails the commit instead.
        try:
            with transaction.atomic():
                self.object.delete()
        except ProtectedError, IntegrityError:
            self.object = self.get_object()  # delete() clears pk even when the commit fails
            return self.render_to_response(self.get_context_data(form=form))
        messages.success(self.request, f"Skill {self.object.name} deleted.")
        return HttpResponseRedirect(self.get_success_url())


class JobDeleteView(AdminDeleteView):
    permission_required = "jobs.delete_jobopening"
    model = JobOpening
    delete_record = staticmethod(delete_job)
    blocker = staticmethod(job_deletion_blocker)
    kind = "job opening"
    warning = (
        "This permanently deletes the job opening and its skill assignments (the skills stay). "
        "It can't be undone."
    )
    success_url = reverse_lazy("jobs:job_list")
