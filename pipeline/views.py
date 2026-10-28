from core.views import placeholder


def application_list(request):
    return placeholder(request, "Applications", phase=4)
