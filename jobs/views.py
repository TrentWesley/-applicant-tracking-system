from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from jobs.forms import JobFilterForm, JobOpeningForm, SkillForm
from jobs.models import JobOpening, Skill


class JobsPermissionMixin(PermissionRequiredMixin):
    # Login is enforced by LoginRequiredMiddleware; a signed-in user without the permission
    # gets 403 instead of a login redirect.
    raise_exception = True


class JobListView(JobsPermissionMixin, ListView):
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


class JobDetailView(JobsPermissionMixin, DetailView):
    permission_required = "jobs.view_jobopening"
    queryset = JobOpening.objects.prefetch_related("skills")
    context_object_name = "job"
    template_name = "jobs/job_detail.html"


class JobCreateView(JobsPermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "jobs.add_jobopening"
    model = JobOpening
    form_class = JobOpeningForm
    template_name = "jobs/job_form.html"
    success_message = "Job opening %(title)s added."


class JobUpdateView(JobsPermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "jobs.change_jobopening"
    model = JobOpening
    form_class = JobOpeningForm
    template_name = "jobs/job_form.html"
    success_message = "Job opening %(title)s: changes saved."


class SkillListView(JobsPermissionMixin, ListView):
    # Recruiters may view skills (they appear on jobs), but this management page is Admin-only.
    permission_required = ("jobs.view_skill", "jobs.change_skill")
    # Meta.ordering is dropped from GROUP BY queries, so order explicitly.
    queryset = Skill.objects.annotate(job_count=Count("jobs")).order_by(*Skill._meta.ordering)
    context_object_name = "skills"
    template_name = "jobs/skill_list.html"


class SkillCreateView(JobsPermissionMixin, SuccessMessageMixin, CreateView):
    permission_required = "jobs.add_skill"
    model = Skill
    form_class = SkillForm
    template_name = "jobs/skill_form.html"
    success_url = reverse_lazy("jobs:skill_list")
    success_message = "Skill %(name)s added."


class SkillUpdateView(JobsPermissionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "jobs.change_skill"
    model = Skill
    form_class = SkillForm
    template_name = "jobs/skill_form.html"
    success_url = reverse_lazy("jobs:skill_list")
    success_message = "Skill renamed to %(name)s."


class SkillDeleteView(JobsPermissionMixin, DeleteView):
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
