"""
JSON:API renderer + parser wiring for v4 admin resources.

Resource endpoints under ``/api/v4/admin/*`` (users, groups, libraries,
flags, failed-imports, custom-covers, age-ratings) render in JSON:API
format (``{data: {type, id, attributes, relationships}, ...}``) per
``tasks/api-v4.md`` Phase 7. Action endpoints (singletons, RPC verbs
like ``/admin/email-settings/test``) keep the camelCase envelope —
they don't fit the resource shape.

The conventional ``Accept: application/vnd.api+json`` header is
honored, but the v4 frontend `api/v4/base.js` already sends
``Accept: application/json``; the renderer below registers under
both media types so admin endpoints respond correctly to either.
"""

from rest_framework_json_api.parsers import JSONParser as _JsonApiJSONParser
from rest_framework_json_api.renderers import (
    JSONRenderer as _JsonApiJSONRenderer,
)


class V4AdminJSONAPIRenderer(_JsonApiJSONRenderer):
    """
    Render admin responses in JSON:API; also serve under ``application/json``.

    Override ``media_type`` so DRF's content-negotiation picks this
    renderer for clients sending the standard JSON Accept header
    (which is what xior emits by default). The wire format stays
    JSON:API.
    """

    media_type = "application/json"
    format = "json"


class V4AdminJSONAPIParser(_JsonApiJSONParser):
    """
    Parse JSON:API request bodies under both media types.

    ``application/json`` rather than the spec's
    ``application/vnd.api+json`` mirrors the renderer override above
    so the frontend's existing xior client (which sends
    ``Content-Type: application/json`` on PATCH/POST) flows in
    through the JSON:API parser without needing a per-call header.
    """

    media_type = "application/json"
