"""codex:api:v4:auth URL Configuration."""

from django.urls import path
from rest_registration.api.views.change_password import ChangePasswordView
from rest_registration.api.views.login import LoginView, LogoutView

from codex.views.auth import AuthToken, CSRFView, ProfileView
from codex.views.register import RegisterView
from codex.views.reset_password import ResetPasswordView, SendResetPasswordLinkView

app_name = "auth"
urlpatterns = [
    path("csrf", CSRFView.as_view(), name="csrf"),
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("token", AuthToken.as_view(), name="token"),
    path("profile", ProfileView.as_view(), name="profile"),
    path(
        "password/reset",
        SendResetPasswordLinkView.as_view(),
        name="password-reset",
    ),
    path(
        "password/reset/confirm",
        ResetPasswordView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/change",
        ChangePasswordView.as_view(),
        name="password-change",
    ),
]
