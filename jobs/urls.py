from django.urls import path

from jobs import views

app_name = "jobs"

urlpatterns = [
    path("jobs/", views.job_list, name="job_list"),
    path("skills/", views.skill_list, name="skill_list"),
]
