"""Serializers for the browser view."""
from zoneinfo import ZoneInfo

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.browser import BrowserCardSerializer
from codex.serializers.mixins import (
    BrowserCardOPDSBaseSerializer,
)
from codex.serializers.models import LanguageSerializer

UTC_TZ = ZoneInfo("UTC")


class OPDS1EntrySerializer(BrowserCardOPDSBaseSerializer):
    """Group OPDS Entry Serializer."""


class OPDS1AcquisitionEntrySerializer(BrowserCardSerializer):
    """Comic OPDS Entry Serializer."""

    size = IntegerField(read_only=True)
    date = DateField(read_only=True)
    updated_at = DateTimeField(read_only=True)
    created_at = DateTimeField(read_only=True)
    summary = CharField(read_only=True)
    comments = CharField(read_only=True)
    notes = CharField(read_only=True)
    publisher_name = CharField(read_only=True)
    language = CharField(read_only=True)


class OPDS1MetadataEntrySerializer(OPDS1AcquisitionEntrySerializer):
    """Comic OPDS Metadata Entry Serializer."""

    # ManyToMany
    ## Categories
    characters = CharField(read_only=True)
    genres = CharField(read_only=True)
    locations = CharField(read_only=True)
    series_groups = CharField(read_only=True)
    story_arcs = CharField(read_only=True)
    tags = CharField(read_only=True)
    teams = CharField(read_only=True)
    ## Contributors
    authors = CharField(read_only=True)
    contributors = CharField(read_only=True)


class OPDS1TemplateLinkSerializer(Serializer):
    """OPDS Link Template Serializer."""

    href = CharField(read_only=True)
    rel = CharField(read_only=True)
    mime_type = CharField(read_only=True)
    title = CharField(read_only=True, required=False)
    length = IntegerField(read_only=True, required=False)
    facet_group = CharField(read_only=True, required=False)
    facet_active = BooleanField(read_only=True, required=False)
    thr_count = IntegerField(read_only=True, required=False)
    pse_count = IntegerField(read_only=True, required=False)
    pse_last_read = IntegerField(read_only=True, required=False)
    pse_last_read_date = DateTimeField(read_only=True, required=False)


class OPDS1TemplateEntrySerializer(Serializer):
    """OPDS Entry Template Serializer."""

    id_tag = CharField(read_only=True)
    title = CharField(read_only=True)
    links = OPDS1TemplateLinkSerializer(many=True, read_only=True)
    issued = DateField(read_only=True, required=False)
    updated = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    published = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    summary = CharField(read_only=True, required=False)
    authors = ListField(child=CharField(), required=False, read_only=True)
    contributors = ListField(child=CharField(), required=False, read_only=True)
    categories = ListField(child=CharField(), required=False, read_only=True)
    publisher = CharField(read_only=True, required=False)
    language = LanguageSerializer(read_only=True, required=False)


class OPDS1TemplateSerializer(Serializer):
    """OPDS Browser Template Serializer."""

    opds_ns = CharField(read_only=True)
    id_tag = CharField(read_only=True)
    title = CharField(read_only=True)
    updated = DateTimeField(read_only=True, default_timezone=UTC_TZ)
    links = OPDS1TemplateLinkSerializer(many=True, read_only=True)
    entries = OPDS1TemplateEntrySerializer(many=True, read_only=True)
    items_per_page = IntegerField(read_only=True)
    total_results = IntegerField(read_only=True)
