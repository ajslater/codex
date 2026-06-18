"""
OPDS Progression 1.0 Serializer.

https://drafts.opds.io/opds-progression-1.0.html
https://drafts.opds.io/schema/progression.schema.json
"""

from rest_framework.fields import (
    CharField,
    DateTimeField,
    FloatField,
    ListField,
)
from rest_framework.serializers import Serializer


class OPDS2ProgressionDeviceSerializer(Serializer):
    """The device that last updated the progression."""

    id = CharField(read_only=True)
    name = CharField(read_only=True)


class OPDS2ProgressionSerializer(Serializer):
    """
    OPDS Progression 1.0 Document.

    https://drafts.opds.io/opds-progression-1.0.html

    Replaces the earlier Readium-locator shape proposed in
    https://github.com/opds-community/drafts/discussions/67 — the formalized
    1.0 draft collapses the locator to a single ``progression`` fraction.
    """

    title = CharField(read_only=True, required=False)
    # ``modified`` is BOTH input and output: GET emits the bookmark's
    # last-update timestamp; PUT clients echo it back so the server can detect
    # a concurrent-update conflict.
    modified = DateTimeField(required=False)
    device = OPDS2ProgressionDeviceSerializer(required=False)
    # Overall reading position as a 0..1 fraction. Output on GET, input on PUT.
    progression = FloatField(required=False, min_value=0, max_value=1)
    references = ListField(child=CharField(), read_only=True, required=False)
