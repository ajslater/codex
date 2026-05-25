"""Admin endpoint for testing online-source credentials."""

from __future__ import annotations

from dataclasses import asdict

from comicbox.online_session import OnlineCredentials
from rest_framework.response import Response

from codex.librarian.onlinetag.credential_validator import (
    KNOWN_SOURCES,
    validate_credentials,
)
from codex.models import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import (
    TaggingValidateRequestSerializer,
    TaggingValidateResponseSerializer,
)
from codex.views.admin.auth import AdminAPIView

_CREDENTIAL_FIELDS = (
    "metron_user",
    "metron_password",
    "metron_url",
    "comicvine_key",
    "comicvine_url",
)


def _merge_credentials(
    defaults: ComicboxTaggingDefaults, overrides: dict[str, str]
) -> OnlineCredentials:
    """Form values win when non-empty; otherwise fall back to stored values."""
    merged = {
        field: overrides[field] or getattr(defaults, field) or ""
        for field in _CREDENTIAL_FIELDS
    }
    return OnlineCredentials(**merged)


class AdminTaggingValidateView(AdminAPIView):
    """POST: validate Metron / Comic Vine credentials."""

    def post(self, request):
        """Validate one or all known sources; return per-source ok/error."""
        request_serializer = TaggingValidateRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data
        overrides = {field: data.get(field, "") for field in _CREDENTIAL_FIELDS}

        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        creds = _merge_credentials(defaults, overrides)

        source = data.get("source") or ""
        targets = {source} if source else KNOWN_SOURCES
        results = validate_credentials(creds, targets)

        response_serializer = TaggingValidateResponseSerializer(
            {"results": {name: asdict(r) for name, r in results.items()}}
        )
        return Response(response_serializer.data)
