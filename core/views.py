from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render


class StaffPermissionMixin(PermissionRequiredMixin):
    """
    Django's PermissionRequiredMixin for every ATS view. Login is enforced by
    LoginRequiredMiddleware, so a signed-in user without the permission gets 403 instead of a
    login redirect.
    """

    raise_exception = True


def dashboard(request):
    return render(request, "core/dashboard.html")


def placeholder(request, title, phase):
    """Stand-in for a section whose pages arrive in a later phase."""
    return render(request, "core/placeholder.html", {"title": title, "phase": phase})
