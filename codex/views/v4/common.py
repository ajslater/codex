"""
Shared v4 view bases, renderers, and helpers.

v4 splits its wire format two ways (see ``tasks/api-v4.md``):

* **View endpoints** (browser, reader, session) use the hand-rolled
  ``{data, meta, errors}`` envelope. Views may either return the
  envelope shape directly or use :func:`envelope` to assemble it.
  :class:`EnvelopeJSONRenderer` passes a fully-formed envelope through
  untouched and wraps everything else.
* **Admin resources** use JSON:API (wired in Phase 7).
"""

from collections.abc import Mapping
from typing import Any, override

from djangorestframework_camel_case.render import CamelCaseJSONRenderer
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.views import APIView

from codex.views.auth import AuthMixin

ENVELOPE_KEYS = frozenset({"data", "meta", "errors"})


class V4CursorPagination(CursorPagination):
    """v4 cursor pagination for admin lists.

    Page-number stays for browser views; admin uses cursor so the
    front-end can stream large user/library/cover lists without
    paying for the offset re-scan. Ordering defaults to ``pk``
    (every admin model has one and it's stably indexed); page size
    is large enough that typical installations land on one page.
    """

    ordering = "pk"
    page_size = 200
    page_size_query_param = "limit"
    max_page_size = 1000


def envelope(
    data: Any = None,
    *,
    meta: Mapping[str, Any] | None = None,
    errors: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a v4 view-endpoint response envelope."""
    return {"data": data, "meta": dict(meta or {}), "errors": list(errors or [])}


class EnvelopeJSONRenderer(CamelCaseJSONRenderer):
    """
    v4 view-endpoint renderer.

    Wraps bare response data in ``{data, meta, errors}`` and applies
    camelCase inflection. Responses whose top-level dict already looks
    like an envelope (any of ``data``/``meta``/``errors`` keys) pass
    through unchanged so views can compose their own meta/errors.

    Error responses raised by DRF (``{"detail": ...}`` shape) are
    rewrapped as a JSON:API-style error object so view-endpoint clients
    see one error shape regardless of source.
    """

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


class V4APIView(AuthMixin, APIView):  # pyright: ignore[reportIncompatibleVariableOverride]
    """v4 view-endpoint base — auth + envelope renderer."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4GenericAPIView(AuthMixin, GenericAPIView):  # pyright: ignore[reportIncompatibleVariableOverride]
    """v4 view-endpoint generic base — auth + envelope renderer."""

    renderer_classes = (EnvelopeJSONRenderer,)
