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

    modified = DateTimeField(read_only=True)
    device = OPDS2ProgressionDeviceSerializer()
    locator = OPDS2ProgressionLocatorSerializer()
