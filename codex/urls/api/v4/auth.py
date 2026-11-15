"""codex:api:v4:auth URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache
from rest_registration.api.views.change_password import ChangePasswordView
from rest_registration.api.views.login import LoginView, LogoutView

from codex.oidc import OIDCLoginRedirectView
from codex.views.api_keys import ApiKeyDetailView, ApiKeyListView
from codex.views.auth import CSRFView, ProfileView, TimezoneView
from codex.views.register import RegisterView
from codex.views.reset_password import ResetPasswordView, SendResetPasswordLinkView

app_name = "auth"
urlpatterns = [
    path("csrf", CSRFView.as_view(), name="csrf"),
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("oidc/login", OIDCLoginRedirectView.as_view(), name="oidc-login"),
    path("keys", never_cache(ApiKeyListView.as_view()), name="keys"),
    path("keys/<int:pk>", never_cache(ApiKeyDetailView.as_view()), name="key"),
    path("profile", ProfileView.as_view(), name="profile"),
    path("timezone", TimezoneView.as_view(), name="timezone"),
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
