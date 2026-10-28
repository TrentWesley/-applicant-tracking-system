from core.roles import admin_required
from core.views import placeholder


def job_list(request):
    return placeholder(request, "Job Openings", phase=3)


@admin_required
def skill_list(request):
    return placeholder(request, "Skills", phase=3)
