"""Admin stats serializers."""

from rest_framework.fields import MultipleChoiceField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    IntegerField,
    Serializer,
)

from codex.serializers.fields import CountDictField


class AdminGroupSerializer(Serializer):
    """Group Counts."""

    publishers_count = IntegerField(required=False, read_only=True)
    imprints_count = IntegerField(required=False, read_only=True)
    series_count = IntegerField(required=False, read_only=True)
    volumes_count = IntegerField(required=False, read_only=True)
    issues_count = IntegerField(required=False, read_only=True)
    folders_count = IntegerField(required=False, read_only=True)
    story_arcs_count = IntegerField(required=False, read_only=True)


class AdminFileTypeSerializer(Serializer):
    """File Type Counts."""

    pdf_count = IntegerField(required=False, read_only=True)
    cbz_count = IntegerField(required=False, read_only=True)
    cbr_count = IntegerField(required=False, read_only=True)
    cbt_count = IntegerField(required=False, read_only=True)
    unknown_count = IntegerField(required=False, read_only=True)


class AdminComicMetadataSerializer(Serializer):
    """Metadata Counts."""

    age_ratings_count = IntegerField(required=False, read_only=True)
    characters_count = IntegerField(required=False, read_only=True)
    contributors_count = IntegerField(required=False, read_only=True)
    contributor_persons_count = IntegerField(required=False, read_only=True)
    contributor_roles_count = IntegerField(required=False, read_only=True)
    countries_count = IntegerField(required=False, read_only=True)
    genres_count = IntegerField(required=False, read_only=True)
    identifiers_count = IntegerField(required=False, read_only=True)
    identifier_types_count = IntegerField(required=False, read_only=True)
    languages_count = IntegerField(required=False, read_only=True)
    locations_count = IntegerField(required=False, read_only=True)
    original_formats_count = IntegerField(required=False, read_only=True)
    series_groups_count = IntegerField(required=False, read_only=True)
    scan_infos_count = IntegerField(required=False, read_only=True)
    story_arcs_count = IntegerField(required=False)
    story_arc_numbers_count = IntegerField(required=False, read_only=True)
    tags_count = IntegerField(required=False, read_only=True)
    taggers_count = IntegerField(required=False, read_only=True)
    teams_count = IntegerField(required=False, read_only=True)


class AdminConfigSerializer(Serializer):
    """Config Information."""

    api_key = CharField(required=False, read_only=True)
    user_groups_count = IntegerField(required=False, read_only=True)
    libraries_count = IntegerField(required=False, read_only=True)
    anonymous_users_count = IntegerField(required=False, read_only=True)
    registered_users_count = IntegerField(required=False, read_only=True)


class AdminSessionsSerializer(Serializer):
    """Session Settings."""

    top_group = CountDictField(required=False, read_only=True)
    order_by = CountDictField(required=False, read_only=True)
    dynamic_covers = CountDictField(required=False, read_only=True)
    finish_on_last_page = CountDictField(required=False, read_only=True)
    fit_to = CountDictField(required=False, read_only=True)
    reading_direction = CountDictField(required=False, read_only=True)


class AdminPlatformSerializer(Serializer):
    """Platform Information."""

    docker = BooleanField(read_only=True)
    machine = CharField(read_only=True)
    cores = IntegerField(read_only=True)
    system = CharField(read_only=True)
    system_release = CharField(read_only=True)
    python = CharField(read_only=True)
    codex = CharField(read_only=True)


class AdminStatsSerializer(Serializer):
    """Admin Stats Tab."""

    platform = AdminPlatformSerializer(required=False)
    config = AdminConfigSerializer(required=False)
    sessions = AdminSessionsSerializer(required=False)
    groups = AdminGroupSerializer(required=False)
    file_types = AdminFileTypeSerializer(required=False)
    metadata = AdminComicMetadataSerializer(required=False)


class AdminStatsRequestSerializer(Serializer):
    """Admin Stats Tab Request."""

    PARAMS_CHOICES = ("groups", "fileTypes", "platform", "config", "groups", "metadata")
    params = MultipleChoiceField(choices=PARAMS_CHOICES, required=False)


class APIKeySerializer(Serializer):
    """API Key."""

    api_key = CharField(source="name")
