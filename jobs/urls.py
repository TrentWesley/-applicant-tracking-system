from django.urls import path

from jobs import views

app_name = "jobs"

urlpatterns = [
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("jobs/new/", views.JobCreateView.as_view(), name="job_create"),
    path("jobs/<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path("jobs/<int:pk>/edit/", views.JobUpdateView.as_view(), name="job_update"),
    path("skills/", views.SkillListView.as_view(), name="skill_list"),
    path("skills/new/", views.SkillCreateView.as_view(), name="skill_create"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_update"),
    path("skills/<int:pk>/delete/", views.SkillDeleteView.as_view(), name="skill_delete"),
]
