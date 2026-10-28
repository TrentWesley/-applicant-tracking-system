from django.shortcuts import render


def dashboard(request):
    return render(request, "core/dashboard.html")


def placeholder(request, title, phase):
    """Stand-in for a section whose pages arrive in a later phase."""
    return render(request, "core/placeholder.html", {"title": title, "phase": phase})
