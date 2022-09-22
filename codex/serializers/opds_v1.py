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
from codex.serializers.models import LanguageSerializer


UTC_TZ = ZoneInfo("UTC")


class OPDSEntrySerializer(BrowserCardOPDSBaseSerializer):
    """Group OPDS Entry Serializer."""


class OPDSAcquisitionEntrySerializer(BrowserCardSerializer):
    """Comic OPDS Entry Serializer."""

    size = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "size")
    date = DateField(read_only=True, source=UNIONFIX_PREFIX + "date")
    updated_at = DateTimeField(read_only=True, source=UNIONFIX_PREFIX + "updated_at")
    created_at = DateTimeField(read_only=True, source=UNIONFIX_PREFIX + "created_at")
    summary = CharField(read_only=True, source=UNIONFIX_PREFIX + "summary")
    comments = CharField(read_only=True, source=UNIONFIX_PREFIX + "comments")
    notes = CharField(read_only=True, source=UNIONFIX_PREFIX + "notes")
    publisher_name = CharField(
        read_only=True, source=UNIONFIX_PREFIX + "publisher_name"
    )
    language = CharField(read_only=True, source=UNIONFIX_PREFIX + "language")

    # ManyToMany
    characters = CharField(source=UNIONFIX_PREFIX + "characters")
    genres = CharField(source=UNIONFIX_PREFIX + "genres")
    locations = CharField(source=UNIONFIX_PREFIX + "locations")
    series_groups = CharField(source=UNIONFIX_PREFIX + "series_groups")
    story_arcs = CharField(source=UNIONFIX_PREFIX + "story_arcs")
    tags = CharField(source=UNIONFIX_PREFIX + "tags")
    teams = CharField(source=UNIONFIX_PREFIX + "teams")
    authors = CharField(source=UNIONFIX_PREFIX + "authors")
    contributors = CharField(source=UNIONFIX_PREFIX + "contributors")


OPDS_COMICS_ORDERED_UNIONFIX_VALUES_MAP = get_serializer_values_map(
    [OPDSAcquisitionEntrySerializer],
)
OPDS_FOLDERS_ORDERED_UNIONFIX_VALUES_MAP = get_serializer_values_map(
    [OPDSAcquisitionEntrySerializer], folders=True
)


OPDS_M2M_FIELDS = (
    "characters",
    "genres",
    "locations",
    "series_groups",
    "story_arcs",
    "tags",
    "teams",
    "credits",
    "credits__role__name",
    "credits__person__name",
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
    links = AuthLinksSerializer(many=True, read_only=True)
    authentication = AuthenticationTypeSerializer(many=True, read_only=True)


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
    links = OPDSTemplateLinkSerializer(many=True, read_only=True)
    issued = DateField(read_only=True, required=False)
    updated = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    published = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    summary = CharField(read_only=True, required=False)
    authors = ListField(child=CharField(), required=False, read_only=True)
    contributors = ListField(child=CharField(), required=False, read_only=True)
    categories = ListField(child=CharField(), required=False, read_only=True)
    publisher = CharField(read_only=True, required=False)
    language = LanguageSerializer(read_only=True, required=False)


class OPDSTemplateSerializer(Serializer):
    """OPDS Browser Template Serializer."""

    opds_ns = CharField(read_only=True)
    id = CharField(read_only=True)
    title = CharField(read_only=True)
    updated = DateTimeField(read_only=True, default_timezone=UTC_TZ)
    links = OPDSTemplateLinkSerializer(many=True, read_only=True)
    entries = OPDSTemplateEntrySerializer(many=True, read_only=True)
    items_per_page = IntegerField(read_only=True)
    total_results = IntegerField(read_only=True)
