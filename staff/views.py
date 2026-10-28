from core.roles import admin_required
from core.views import placeholder


@admin_required
def staff_list(request):
    return placeholder(request, "Staff Management", phase=11)
