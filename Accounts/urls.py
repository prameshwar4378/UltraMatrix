from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("signup/", views.school_signup, name="school_signup"),
    path("features/", views.feature_onboarding, name="feature_onboarding"),
    path(
        "login/",
        views.SchoolLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),
]
