from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView

from core.roles import role_name
from core.views import StaffPermissionMixin
from staff.forms import StaffCreateForm
from staff.services import (
    ROLES,
    StaffChangeRefused,
    active_admin_ids,
    change_role,
    deactivate_staff,
    deactivation_blocker,
    display_name,
    reactivate_staff,
    role_change_blocker,
    with_article,
)

LIST_URL = reverse_lazy("staff:staff_list")


class StaffListView(StaffPermissionMixin, ListView):
    """Active staff, or (with ?show=inactive) everyone. Only allowed actions are rendered."""

    permission_required = ("auth.view_user", "auth.change_user")
    context_object_name = "staff"
    template_name = "staff/staff_list.html"

    def get_queryset(self):
        self.show_inactive = self.request.GET.get("show") == "inactive"
        users = User.objects.order_by("first_name", "last_name", "username")
        return users if self.show_inactive else users.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(show_inactive=self.show_inactive, **kwargs)
        admin_ids = active_admin_ids()  # one query for every row's last-Admin check
        by = self.request.user
        for user in context["staff"]:
            user.role = role_name(user)
            user.can_deactivate = deactivation_blocker(user, by, admin_ids) is None
            user.new_roles = [
                role for role in ROLES if role_change_blocker(user, role, by, admin_ids) is None
            ]
        return context


class StaffCreateView(StaffPermissionMixin, CreateView):
    permission_required = ("auth.view_user", "auth.add_user")
    form_class = StaffCreateForm
    template_name = "staff/staff_form.html"
    success_url = LIST_URL

    def form_valid(self, form):
        response = super().form_valid(form)
        role = with_article(form.cleaned_data["role"])
        name = display_name(self.object)
        messages.success(self.request, f"Staff account {name} created as {role}.")
        return response


class StaffActionView(StaffPermissionMixin, View):
    """
    POST-only Deactivate, Reactivate or Change role from the staff list, which reloads with the
    outcome (back on the inactive view when the form came from there). A refusal changes nothing.
    """

    permission_required = ("auth.view_user", "auth.change_user")
    http_method_names = ["post"]

    def change(self, user):
        """Apply the action through the staff service and return the success message."""
        raise NotImplementedError

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            text = self.change(user)
        except StaffChangeRefused as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(request, text)
        url = str(LIST_URL)
        if request.POST.get("show") == "inactive":
            url = f"{url}?show=inactive"
        return HttpResponseRedirect(url)


class StaffDeactivateView(StaffActionView):
    def change(self, user):
        deactivate_staff(user, by=self.request.user)
        name = display_name(user)
        return f"{name} deactivated. They can no longer log in; their history is kept."


class StaffReactivateView(StaffActionView):
    def change(self, user):
        reactivate_staff(user)
        return f"{display_name(user)} reactivated. They can log in again."


class StaffRoleView(StaffActionView):
    def change(self, user):
        role = self.request.POST.get("role", "")
        change_role(user, role, by=self.request.user)
        return f"{display_name(user)} is now {with_article(role)}."
