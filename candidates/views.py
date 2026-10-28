from core.views import placeholder


def candidate_list(request):
    return placeholder(request, "Candidates", phase=2)
