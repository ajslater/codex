"""codex:api:v4:auth URL Configuration."""

from django.urls import path

from codex.views.v4.auth import (
    V4ChangePasswordView,
    V4CSRFView,
    V4LoginView,
    V4LogoutView,
    V4ProfileView,
    V4RegisterView,
    V4ResetPasswordView,
    V4SendResetPasswordLinkView,
    V4TokenView,
)

app_name = "auth"
urlpatterns = [
    path("csrf", V4CSRFView.as_view(), name="csrf"),
    path("register", V4RegisterView.as_view(), name="register"),
    path("login", V4LoginView.as_view(), name="login"),
    path("logout", V4LogoutView.as_view(), name="logout"),
    path("token", V4TokenView.as_view(), name="token"),
    path("profile", V4ProfileView.as_view(), name="profile"),
    path(
        "password/reset",
        V4SendResetPasswordLinkView.as_view(),
        name="password-reset",
    ),
    path(
        "password/reset/confirm",
        V4ResetPasswordView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/change",
        V4ChangePasswordView.as_view(),
        name="password-change",
    ),
]
