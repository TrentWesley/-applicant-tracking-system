from django.urls import path

from candidates import views

app_name = "candidates"

urlpatterns = [
    path("", views.CandidateListView.as_view(), name="candidate_list"),
    path("archived/", views.ArchivedCandidateListView.as_view(), name="candidate_archived_list"),
    path("new/", views.CandidateCreateView.as_view(), name="candidate_create"),
    path("<int:pk>/", views.CandidateDetailView.as_view(), name="candidate_detail"),
    path("<int:pk>/edit/", views.CandidateUpdateView.as_view(), name="candidate_update"),
    path("<int:pk>/archive/", views.CandidateArchiveView.as_view(), name="candidate_archive"),
    path("<int:pk>/restore/", views.CandidateRestoreView.as_view(), name="candidate_restore"),
    path("<int:pk>/delete/", views.CandidateDeleteView.as_view(), name="candidate_delete"),
]
