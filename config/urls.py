from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.forms import LoginForm

urlpatterns = [
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=LoginForm),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("candidates/", include("candidates.urls")),
    path("", include("jobs.urls")),
    path("applications/", include("pipeline.urls")),
    path("staff/", include("staff.urls")),
]
