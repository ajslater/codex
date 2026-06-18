"""
OPDS 2.0 JSON renderers.

OPDS 2.0 puts the feed / publication object at the JSON root. Codex's default
view renderer (:class:`codex.views.envelope.EnvelopeJSONRenderer`) wraps every
response in ``{data, meta, errors}`` for the SPA — which is *not* a valid OPDS
2.0 document and is rejected by strict clients (e.g. Stump). These renderers
emit the object at the root, still camelCased to match the schemas' key names,
with the correct OPDS media types.
"""

from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from codex.views.opds.const import MimeType


class OPDS2FeedRenderer(CamelCaseJSONRenderer):
    """Root-level camelCase JSON served as ``application/opds+json``."""

    media_type = MimeType.OPDS_JSON


class OPDS2ManifestRenderer(CamelCaseJSONRenderer):
    """Publication manifest served as ``application/divina+json``."""

    media_type = MimeType.DIVINA
