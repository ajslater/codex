"""
API v4 auth endpoints — thin envelope wrappers over v3/rest-registration.

Most v4 auth verbs reuse the v3 / rest-registration view bodies; v4
just overlays :class:`EnvelopeJSONRenderer` so responses ship in
``{data, meta, errors}``. The exceptions are :class:`V4CSRFView`
(new — explicit cookie-bootstrap endpoint) and the profile endpoint,
which is rebuilt as a v4 native view so the writable surface is
explicit instead of inherited from rest-registration's plug-in
serializer.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_registration.api.views.change_password import (
    ChangePasswordView as _ChangePasswordView,
)
from rest_registration.api.views.login import LoginView as _LoginView
from rest_registration.api.views.login import LogoutView as _LogoutView

from codex.serializers.v4.auth import (
    V4ProfileUpdateSerializer,
    V4UserSerializer,
)
from codex.views.auth import AuthToken as _AuthToken
from codex.views.register import RegisterView as _RegisterView
from codex.views.reset_password import (
    ResetPasswordView as _ResetPasswordView,
)
from codex.views.reset_password import (
    SendResetPasswordLinkView as _SendResetPasswordLinkView,
)
from codex.views.v4.common import EnvelopeJSONRenderer, envelope


class _V4AuthMixin:
    """Common v4 auth wrapper: apply the envelope renderer."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4RegisterView(_V4AuthMixin, _RegisterView):
    """POST /api/v4/auth/register — wraps Codex's flag-aware register flow."""


class V4LoginView(_V4AuthMixin, _LoginView):
    """POST /api/v4/auth/login."""


class V4LogoutView(_V4AuthMixin, _LogoutView):
    """POST /api/v4/auth/logout."""


class V4TokenView(_V4AuthMixin, _AuthToken):
    """GET (issue) + PUT (rotate) the user's API token."""


class V4SendResetPasswordLinkView(_V4AuthMixin, _SendResetPasswordLinkView):
    """POST /api/v4/auth/password/reset — request a reset-link email."""


class V4ResetPasswordView(_V4AuthMixin, _ResetPasswordView):
    """POST /api/v4/auth/password/reset/confirm — apply the new password."""


class V4ChangePasswordView(_V4AuthMixin, _ChangePasswordView):
    """POST /api/v4/auth/password/change — authenticated change."""


@method_decorator(ensure_csrf_cookie, name="get")
class V4CSRFView(APIView):
    """
    ``GET /api/v4/auth/csrf`` — bootstrap the CSRF cookie.

    Replaces v3's implicit cookie-via-profile bootstrap. The
    ``ensure_csrf_cookie`` decorator forces Django to set the cookie on
    the response; the body just confirms the token value so a client
    can ferry it as a header on the next mutating request without
    waiting for a second round trip.
    """

    renderer_classes = (EnvelopeJSONRenderer,)
    permission_classes = ()

    def get(self, request) -> Response:
        """Return the active CSRF token; cookie is set as a side effect."""
        return Response(envelope({"csrfToken": get_token(request)}))


class V4ProfileView(APIView):
    """``GET`` and ``PATCH /api/v4/auth/profile`` — current user."""

    renderer_classes = (EnvelopeJSONRenderer,)
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _payload(user) -> dict:
        return {
            "id": user.pk,
            "username": user.get_username(),
            "email": getattr(user, "email", "") or "",
            "is_staff": bool(getattr(user, "is_staff", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
        }

    def get(self, request, *args, **kwargs) -> Response:
        """Return the authenticated user's profile."""
        if not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated
        data = V4UserSerializer(self._payload(request.user)).data
        return Response(envelope(data))

    def patch(self, request, *args, **kwargs) -> Response:
        """
        Apply a partial profile update.

        Accepts ``username`` (unless remote-user auth owns identity),
        ``email`` (blank → cleared), and ``timezone`` (stored on the
        session, same as the v3 timezone endpoint).
        """
        if not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated
        serializer = V4ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        user = request.user
        user_model = get_user_model()
        updated_fields: list[str] = []
        username = validated.get("username")
        if username and not settings.AUTH_REMOTE_USER:
            username_field = getattr(user_model, "USERNAME_FIELD", "username")
            setattr(user, username_field, username)
            updated_fields.append(username_field)
        if "email" in validated:
            user.email = validated["email"]
            updated_fields.append("email")
        if updated_fields:
            user.save(update_fields=updated_fields)

        timezone = validated.get("timezone")
        if timezone:
            session = request.session
            session["django_timezone"] = timezone
            session.save()

        data = V4UserSerializer(self._payload(user)).data
        return Response(envelope(data))
