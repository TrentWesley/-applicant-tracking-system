from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.views.generic import DeleteView, TemplateView

from core.dashboard import dashboard_context
from core.deletion import DeleteRefused


class StaffPermissionMixin(PermissionRequiredMixin):
    """
    Django's PermissionRequiredMixin for every ATS view. Login is enforced by
    LoginRequiredMiddleware, so a signed-in user without the permission gets 403 instead of a
    login redirect.
    """

    raise_exception = True


class DashboardView(StaffPermissionMixin, TemplateView):
    """The start page for both roles. It only reads (core/dashboard.py)."""

    permission_required = (
        "candidates.view_candidate",
        "jobs.view_jobopening",
        "pipeline.view_application",
    )
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**dashboard_context(), **kwargs)


class AdminDeleteView(StaffPermissionMixin, DeleteView):
    """
    Permanent delete with a confirmation step: GET shows the confirmation page (or why the record
    can't be deleted), POST deletes through `delete_record` and redirects with a message. A
    refusal re-renders the page with the reason; nothing is removed. Subclasses set
    `permission_required` (a delete permission, which only Admins have), `model`,
    `delete_record`, `blocker`, `kind`, `warning` and `success_url`.
    """

    template_name = "core/confirm_delete.html"
    delete_record = None  # service function: deletes or raises DeleteRefused
    blocker = None  # function: why the record can't be deleted now, or None
    kind = ""  # "candidate", "job opening", "application"
    warning = ""

    def get_context_data(self, refusal=None, **kwargs):
        return super().get_context_data(
            refusal=refusal or self.blocker(self.object),
            kind=self.kind,
            warning=self.warning,
            **kwargs,
        )

    def form_valid(self, form):
        name = str(self.object)
        try:
            self.delete_record(self.object)
        except DeleteRefused as refusal:
            if refusal.gone:
                messages.error(self.request, str(refusal))
                return HttpResponseRedirect(self.get_success_url())
            return self.render_to_response(self.get_context_data(refusal=str(refusal)))
        messages.success(self.request, f"{self.kind.capitalize()} {name} deleted.")
        return HttpResponseRedirect(self.get_success_url())
