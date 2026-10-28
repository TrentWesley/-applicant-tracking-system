from django.urls import path

from pipeline import views

app_name = "pipeline"

urlpatterns = [
    path("", views.application_list, name="application_list"),
]
