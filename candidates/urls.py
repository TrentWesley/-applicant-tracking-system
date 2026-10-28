from django.urls import path

from candidates import views

app_name = "candidates"

urlpatterns = [
    path("", views.CandidateListView.as_view(), name="candidate_list"),
    path("new/", views.CandidateCreateView.as_view(), name="candidate_create"),
    path("<int:pk>/", views.CandidateDetailView.as_view(), name="candidate_detail"),
    path("<int:pk>/edit/", views.CandidateUpdateView.as_view(), name="candidate_update"),
]
