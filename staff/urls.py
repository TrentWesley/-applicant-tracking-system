from django.urls import path

from staff import views

app_name = "staff"

urlpatterns = [
    path("", views.staff_list, name="staff_list"),
]
