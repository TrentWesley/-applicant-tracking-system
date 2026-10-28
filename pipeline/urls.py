from django.urls import path

from pipeline import views

app_name = "pipeline"

urlpatterns = [
    path("", views.ApplicationListView.as_view(), name="application_list"),
    path("new/", views.ApplicationCreateView.as_view(), name="application_create"),
    path("<int:pk>/", views.ApplicationDetailView.as_view(), name="application_detail"),
]
