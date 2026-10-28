from django.urls import path

from candidates import views

app_name = "candidates"

urlpatterns = [
    path("", views.candidate_list, name="candidate_list"),
]
