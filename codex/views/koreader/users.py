"""KOReader kosync user and health endpoints."""

from http import HTTPStatus

from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from codex.views.koreader.base import (
    ERROR_REGISTRATION_DISABLED,
    KOSyncAPIView,
    kosync_error,
)


class KOSyncUsersAuthView(KOSyncAPIView):
    """``GET users/auth``: check the device's credentials."""

    def get(self, *_args, **_kwargs) -> Response:
        """Report success: authentication has already passed."""
        return Response({"authorized": "OK"})


class KOSyncUsersCreateView(KOSyncAPIView):
    """``POST users/create``: Codex users are made in Codex, not on a device."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, *_args, **_kwargs) -> Response:
        """Refuse registration."""
        return kosync_error(
            HTTPStatus.PAYMENT_REQUIRED,
            ERROR_REGISTRATION_DISABLED,
            "User registration is disabled.",
        )


class KOSyncHealthcheckView(KOSyncAPIView):
    """``GET healthcheck``."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, *_args, **_kwargs) -> Response:
        """Report the sync service is up."""
        return Response({"state": "OK"})
