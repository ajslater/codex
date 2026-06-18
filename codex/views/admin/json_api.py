"""
JSON:API renderer + parser wiring for admin resources.

Admin *resource* viewsets (users, groups, libraries, flags, failed-
imports, custom-covers, age-ratings) render in JSON:API format
(``{data: {type, id, attributes, relationships}, ...}``). Action
endpoints (singletons, RPC verbs like
``/admin/email-settings/test``) stay on the camelCase envelope —
JSON:API's resource shape doesn't fit verb endpoints.

The conventional ``Accept: application/vnd.api+json`` header is
honored, but the frontend's xior client sends
``Accept: application/json``; the renderer below registers under
both media types so admin endpoints respond correctly to either.
"""

from rest_framework_json_api.parsers import JSONParser as _JsonApiJSONParser
from rest_framework_json_api.renderers import (
    JSONRenderer as _JsonApiJSONRenderer,
)

from codex.views.envelope import EnvelopeJSONRenderer
from codex.views.pagination import CodexCursorPagination


class AdminJSONAPIRenderer(_JsonApiJSONRenderer):
    """Render admin responses in JSON:API; also serve under ``application/json``."""

    media_type = "application/json"
    format = "json"


class AdminJSONAPIParser(_JsonApiJSONParser):
    """Parse JSON:API request bodies under both media types."""

    media_type = "application/json"


class AdminEnvelopeMixin:
    """
    Camel-case envelope renderer + cursor pagination for action admins.

    Singleton endpoints (stats, email-settings, throttle-settings) and
    RPC verbs (``/admin/email-settings/test``, ``/admin/tag-write``)
    wear this so their wire shape matches the rest of the view
    endpoints. Pagination is set unconditionally; APIViews ignore it.
    """

    renderer_classes = (EnvelopeJSONRenderer,)
    pagination_class = CodexCursorPagination


class AdminJsonApiMixin(AdminEnvelopeMixin):
    """JSON:API renderer + parser for admin *resource* viewsets."""

    renderer_classes = (AdminJSONAPIRenderer,)  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    parser_classes = (AdminJSONAPIParser,)
