"""Serializers for the browser view."""

from zoneinfo import ZoneInfo

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DictField,
    IntegerField,
    Serializer,
)

from codex.serializers.models.pycountry import LanguageSerializer

UTC_TZ = ZoneInfo("UTC")


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


class OPDS1ContributorSerializer(Serializer):
    """OPDS 1 Contributor."""

    name = CharField(read_only=True)
    url = CharField(read_only=True, required=False)


class OPDS1TemplateEntrySerializer(Serializer):
    """OPDS Entry Template Serializer."""

    id_tag = CharField(read_only=True)
    title = CharField(read_only=True)
    links = OPDS1TemplateLinkSerializer(many=True, read_only=True)
    issued = DateField(read_only=True, required=False)
    updated = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    published = DateTimeField(read_only=True, required=False, default_timezone=UTC_TZ)
    publisher = CharField(read_only=True, required=False)
    language = LanguageSerializer(read_only=True, required=False)
    summary = CharField(read_only=True, required=False)
    authors = OPDS1ContributorSerializer(many=True, required=False, read_only=True)
    contributors = OPDS1ContributorSerializer(many=True, required=False, read_only=True)
    category_groups = DictField(required=False, read_only=True)


class OPDS1TemplateSerializer(Serializer):
    """OPDS Browser Template Serializer."""

    opds_ns = CharField(read_only=True)
    is_acquisition = BooleanField(read_only=True)
    id_tag = CharField(read_only=True)
    title = CharField(read_only=True)
    updated = DateTimeField(read_only=True, default_timezone=UTC_TZ)
    links = OPDS1TemplateLinkSerializer(many=True, read_only=True)
    entries = OPDS1TemplateEntrySerializer(many=True, read_only=True)
    items_per_page = IntegerField(read_only=True)
    total_results = IntegerField(read_only=True)
