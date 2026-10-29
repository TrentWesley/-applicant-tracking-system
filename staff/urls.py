from django.urls import path

from staff import views

app_name = "staff"

urlpatterns = [
    path("", views.StaffListView.as_view(), name="staff_list"),
    path("new/", views.StaffCreateView.as_view(), name="staff_create"),
    path("<int:pk>/role/", views.StaffRoleView.as_view(), name="staff_role"),
    path("<int:pk>/deactivate/", views.StaffDeactivateView.as_view(), name="staff_deactivate"),
    path("<int:pk>/reactivate/", views.StaffReactivateView.as_view(), name="staff_reactivate"),
]
