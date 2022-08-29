"""Serializers for the browser view."""
from zoneinfo import ZoneInfo

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    JSONField,
    ListField,
    Serializer,
)

from codex.serializers.browser import BrowserCardSerializer
from codex.serializers.mixins import (
    UNIONFIX_PREFIX,
    BrowserCardOPDSBaseSerializer,
    get_serializer_values_map,
)


UTC_TZ = ZoneInfo("UTC")


class OPDSEntrySerializer(BrowserCardOPDSBaseSerializer):
    """Browse card displayed in the browser."""

    size = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "size")
    date = DateField(read_only=True, source=UNIONFIX_PREFIX + "date")
    summary = CharField(read_only=True, source=UNIONFIX_PREFIX + "summary")
    updated_at = DateTimeField(read_only=True, source=UNIONFIX_PREFIX + "updated_at")
    #
    # authors, category, dc:identifier SOME CVID?


BROWSER_CARD_AND_OPDS_ORDERED_UNIONFIX_VALUES_MAP = get_serializer_values_map(
    [BrowserCardSerializer, OPDSEntrySerializer]
)


class AuthenticationTypeSerializer(Serializer):
    """OPDS Authentication Type."""

    type = CharField(read_only=True)
    labels = JSONField(read_only=True)


class AuthLinksSerializer(Serializer):
    """OPDS Authentication Links."""

    rel = CharField(read_only=True)
    href = CharField(read_only=True)
    type = CharField(read_only=True)
    width = IntegerField(read_only=True, required=False)
    height = IntegerField(read_only=True, required=False)


class AuthenticationSerializer(Serializer):
    """OPDS Authentication Document."""

    id = CharField(read_only=True)
    title = CharField(read_only=True)
    description = CharField(read_only=True)
    links = ListField(child=AuthLinksSerializer())
    authentication = ListField(child=AuthenticationTypeSerializer())


class OPDSTemplateLinkSerializer(Serializer):
    """OPDS Link Template Serializer."""

    href = CharField(read_only=True)
    rel = CharField(read_only=True)
    type = CharField(read_only=True)
    title = CharField(read_only=True, required=False)
    length = IntegerField(read_only=True, required=False)
    facet_group = CharField(read_only=True, required=False)
    facet_active = BooleanField(read_only=True, required=False)
    thr_count = IntegerField(read_only=True, required=False)
    pse_count = IntegerField(read_only=True, required=False)
    pse_last_read = IntegerField(read_only=True, required=False)


class OPDSTemplateEntrySerializer(Serializer):
    """OPDS Entry Template Serializer."""

    id = CharField(read_only=True)
    title = CharField(read_only=True)
    links = ListField(child=OPDSTemplateLinkSerializer(), read_only=True)
    issued = DateField(read_only=True, required=False)
    updated = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    summary = CharField(read_only=True, required=False)


class OPDSTemplateSerializer(Serializer):
    """OPDS Browser Template Serializer."""

    opds_ns = CharField(read_only=True)
    id = CharField(read_only=True)
    title = CharField(read_only=True)
    updated = DateTimeField(read_only=True, default_timezone=UTC_TZ)
    links = ListField(child=OPDSTemplateLinkSerializer(), read_only=True)
    entries = ListField(child=OPDSTemplateEntrySerializer(), read_only=True)
