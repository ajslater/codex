"""
View-endpoint response envelope.

Codex view endpoints (browser, reader, session, favorites, etc.)
wrap their JSON responses in ``{data, meta, errors}``. The renderer
below makes that wrap automatic — bare data gets wrapped; payloads
that already look like an envelope pass through so views can
compose their own meta / errors.

Errors raised by DRF (``{"detail": ...}`` shape) are reshaped into
a JSON:API-style error object so view-endpoint clients see one
error shape regardless of source.

Admin resource viewsets render JSON:API instead — see
:mod:`codex.views.admin.json_api`.
"""

from collections.abc import Mapping
from typing import Any, override

from djangorestframework_camel_case.render import CamelCaseJSONRenderer

ENVELOPE_KEYS = frozenset({"data", "meta", "errors"})


def envelope(
    data: Any = None,
    *,
    meta: Mapping[str, Any] | None = None,
    errors: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a view-endpoint response envelope."""
    return {"data": data, "meta": dict(meta or {}), "errors": list(errors or [])}


class EnvelopeJSONRenderer(CamelCaseJSONRenderer):
    """View-endpoint renderer: wrap in ``{data, meta, errors}`` + camelCase."""

    format = "json"

    @override
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Wrap ``data`` in the envelope then defer to camelCase serialization."""
        payload = self._wrap(data, renderer_context)
        return super().render(payload, accepted_media_type, renderer_context)

    @staticmethod
    def _wrap(data, renderer_context):
        if isinstance(data, Mapping) and ENVELOPE_KEYS & set(data.keys()):
            base = {"data": None, "meta": {}, "errors": []}
            base.update(data)
            return base
        if EnvelopeJSONRenderer._looks_like_drf_error(data, renderer_context):
            return {
                "data": None,
                "meta": {},
                "errors": [EnvelopeJSONRenderer._error_object(data, renderer_context)],
            }
        return {"data": data, "meta": {}, "errors": []}

    @staticmethod
    def _looks_like_drf_error(data, renderer_context) -> bool:
        if not renderer_context:
            return False
        response = renderer_context.get("response")
        if response is None or response.status_code < 400:  # noqa: PLR2004
            return False
        return isinstance(data, Mapping)

    @staticmethod
    def _error_object(data: Mapping[str, Any], renderer_context) -> dict[str, Any]:
        response = renderer_context["response"]
        status = str(response.status_code)
        detail = data.get("detail") if "detail" in data else data
        return {
            "status": status,
            "title": response.reason_phrase or "",
            "detail": detail,
        }
