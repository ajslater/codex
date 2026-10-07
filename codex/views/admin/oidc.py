"""Admin OIDC Settings View."""

import requests
from django.core.cache import cache
from loguru import logger
from rest_framework.response import Response

from codex.models import OIDCSettings
from codex.oidc import DISCOVERY_CACHE_KEY, fetch_discovery_document
from codex.serializers.admin.oidc import (
    OIDCSettingsSerializer,
    OIDCTestRequestSerializer,
    OIDCTestResponseSerializer,
)
from codex.views.admin.auth import AdminAPIView


class AdminOIDCSettingsView(AdminAPIView):
    """GET/PUT for the OIDCSettings singleton."""

    def get(self, _request):
        """Return the current OIDC settings."""
        row = OIDCSettings.objects.get(pk=1)
        serializer = OIDCSettingsSerializer(row)
        return Response(serializer.data)

    def put(self, request):
        """Update OIDC settings and drop the cached discovery document."""
        row = OIDCSettings.objects.get(pk=1)
        serializer = OIDCSettingsSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # The issuer may have changed; the next login or logout-URL
        # build must re-discover the provider's endpoints.
        cache.delete(DISCOVERY_CACHE_KEY)
        return Response(OIDCSettingsSerializer(row).data)


class AdminOIDCTestView(AdminAPIView):
    """POST a discovery-document probe against the identity provider."""

    def post(self, request):
        """Fetch the discovery document and report the advertised endpoints."""
        req = OIDCTestRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        server_url = req.validated_data.get("server_url", "")
        if not server_url:
            row = OIDCSettings.objects.filter(pk=1).first()
            server_url = row.server_url if row else ""
        if not server_url:
            response = OIDCTestResponseSerializer(
                {"ok": False, "error": "No server URL configured."}
            )
            return Response(response.data)

        try:
            doc = fetch_discovery_document(server_url)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Codex OIDC test connection failed: {exc}", exc=exc)
            response = OIDCTestResponseSerializer(
                {"ok": False, "error": str(exc) or exc.__class__.__name__}
            )
            return Response(response.data)

        response = OIDCTestResponseSerializer(
            {
                "ok": bool(
                    doc.get("authorization_endpoint") and doc.get("token_endpoint")
                ),
                "issuer": doc.get("issuer"),
                "authorization_endpoint": bool(doc.get("authorization_endpoint")),
                "token_endpoint": bool(doc.get("token_endpoint")),
                "userinfo_endpoint": bool(doc.get("userinfo_endpoint")),
                "end_session_endpoint": bool(doc.get("end_session_endpoint")),
            }
        )
        return Response(response.data)
