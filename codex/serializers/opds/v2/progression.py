"""
OPDS v2 Progression Serializer.

https://github.com/opds-community/drafts/discussions/67
"""

from rest_framework.fields import (
    CharField,
    DateTimeField,
    FloatField,
    IntegerField,
    ListField,
)
from rest_framework.serializers import Serializer


class OPDS2ProgressionDeviceSerializer(Serializer):
    """Progression Device Element."""

    id = CharField(read_only=True)
    name = CharField(read_only=True)


class OPDS2ProgressionLocationsSerializer(Serializer):
    """Progression Location Element."""

    fragments = ListField(child=CharField(read_only=True), read_only=True)
    position = IntegerField()
    progression = FloatField(read_only=True)
    total_progression = FloatField(read_only=True)


class OPDS2ProgressionLocatorSerializer(Serializer):
    """Progression Locator Element."""

    title = CharField(read_only=True)
    href = CharField(read_only=True)
    type = CharField(read_only=True)
    locations = OPDS2ProgressionLocationsSerializer()


class OPDS2ProgressionSerializer(Serializer):
    """
    Progression.

    https://github.com/opds-community/drafts/discussions/67#discussioncomment-6414507
    """

    # ``modified`` is BOTH input and output: the GET response emits the
    # bookmark's last-update timestamp, and the spec asks PUT clients to
    # echo it back so the server can detect concurrent-update conflicts.
    # Was previously ``read_only=True`` which silently dropped the field
    # from PUT validated_data, making the view's conflict check
    # unreachable (sub-plan 06 #1).
    modified = DateTimeField(required=False)
    device = OPDS2ProgressionDeviceSerializer()
    locator = OPDS2ProgressionLocatorSerializer()
