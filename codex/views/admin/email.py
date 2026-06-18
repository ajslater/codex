"""Admin Email Settings View."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from loguru import logger
from rest_framework.response import Response

from codex.models import EmailSettings
from codex.serializers.admin.email import (
    EmailSettingsSerializer,
    EmailTestSendRequestSerializer,
    EmailTestSendResponseSerializer,
)
from codex.settings.db import email_enabled, get_email_from_address
from codex.startup.registration import patch_registration_setting
from codex.views.admin.auth import AdminAPIView


class AdminEmailSettingsView(AdminAPIView):
    """GET/PUT for the EmailSettings singleton."""

    def get(self, _request):
        """Return the current email settings."""
        row = EmailSettings.objects.get(pk=1)
        serializer = EmailSettingsSerializer(row)
        return Response(serializer.data)

    def put(self, request):
        """Update email settings and refresh dependent feature gates."""
        row = EmailSettings.objects.get(pk=1)
        serializer = EmailSettingsSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Email may have just been turned on/off — refresh
        # rest-registration's verification flags to match.
        patch_registration_setting()
        return Response(EmailSettingsSerializer(row).data)


def _resolve_test_send_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Build SMTP connection kwargs from form overrides + saved row + settings.

    Mirrors the "Test" pattern used by the tagging defaults page: the
    form values take precedence so an admin can validate creds before
    saving them. Anything not in the form falls back to the saved row
    (via the DB-aware backend) and then to Django settings.
    """
    kwargs: dict[str, Any] = {}
    # Map serializer field name → EmailBackend constructor kwarg.
    keymap = {
        "host": "host",
        "port": "port",
        "user": "username",
        "password": "password",
        "use_tls": "use_tls",
        "use_ssl": "use_ssl",
        "timeout": "timeout",
    }
    for src, dest in keymap.items():
        if src in payload:
            kwargs[dest] = payload[src]
    return kwargs


def _resolve_from_address(payload: dict[str, Any]) -> str:
    """Sender for the test send — form override, then live settings fallback."""
    candidate = payload.get("from_address") or payload.get("user")
    if candidate:
        return candidate
    return get_email_from_address()


def _resolve_subject_prefix(payload: dict[str, Any]) -> str:
    """Subject prefix — form override, then settings."""
    if "subject_prefix" in payload:
        return payload["subject_prefix"]
    row = EmailSettings.objects.filter(pk=1).first()
    if row is not None and row.subject_prefix:
        return row.subject_prefix
    return settings.EMAIL_SUBJECT_PREFIX


class AdminEmailTestSendView(AdminAPIView):
    """POST a test message through the configured SMTP backend."""

    def post(self, request):
        """Send a test email and report success/error."""
        req = EmailTestSendRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        payload = req.validated_data
        recipient = payload["recipient"]

        from_address = _resolve_from_address(payload)
        if not from_address:
            response = EmailTestSendResponseSerializer(
                {"ok": False, "error": "No sender address configured."}
            )
            return Response(response.data)

        conn_kwargs = _resolve_test_send_kwargs(payload)
        # Without a host, both the form override and the saved/settings
        # fallback are empty — there is nothing to send through.
        # ``email_enabled`` covers the saved+settings case;
        # ``conn_kwargs`` covers the form-only override case.
        if not conn_kwargs.get("host") and not email_enabled():
            response = EmailTestSendResponseSerializer(
                {"ok": False, "error": "No SMTP host configured."}
            )
            return Response(response.data)

        subject_prefix = _resolve_subject_prefix(payload)
        try:
            with get_connection(**conn_kwargs) as connection:
                message = EmailMessage(
                    subject=f"{subject_prefix}Test message",
                    body=(
                        "This is a test message from Codex confirming that your "
                        "SMTP configuration works."
                    ),
                    from_email=from_address,
                    to=[recipient],
                    connection=connection,
                )
                sent = message.send(fail_silently=False)
        except Exception as exc:
            logger.warning("Codex Email test send failed: {exc}", exc=exc)
            response = EmailTestSendResponseSerializer(
                {"ok": False, "error": str(exc) or exc.__class__.__name__}
            )
            return Response(response.data)

        if not sent:
            response = EmailTestSendResponseSerializer(
                {"ok": False, "error": "Backend reported no messages sent."}
            )
            return Response(response.data)

        response = EmailTestSendResponseSerializer({"ok": True})
        return Response(response.data)
