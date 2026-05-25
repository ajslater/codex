"""codex:api:v3:auth URL Configuration."""

from django.urls import include, path

from codex.views.auth import AuthToken
from codex.views.public import AdminFlagsView
from codex.views.register import RegisterView
from codex.views.reset_password import (
    ResetPasswordView,
    SendResetPasswordLinkView,
)
from codex.views.timezone import TimezoneView

app_name = "auth"
urlpatterns = [
    # Codex overrides; matched before rest-registration's include so
    # they take precedence. The register view checks AdminFlags at
    # request time; the reset-password views add rate-limiting.
    path("register/", RegisterView.as_view(), name="register"),
    path(
        "send-reset-password-link/",
        SendResetPasswordLinkView.as_view(),
        name="send-reset-password-link",
    ),
    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password",
    ),
    path("", include("rest_registration.api.urls")),
    path("flags/", AdminFlagsView.as_view(), name="flags"),
    path("token/", AuthToken.as_view(), name="token"),
    path("timezone/", TimezoneView.as_view(), name="timezone"),
]
