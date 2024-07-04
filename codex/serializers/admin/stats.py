"""Admin stats serializers."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    IntegerField,
    Serializer,
)

from codex.serializers.fields import (
    CountDictField,
    SerializerChoicesField,
    StringListMultipleChoiceField,
)

FILE_TYPES_CHOICES = ("CBZ", "CBR", "CBT", "PDF", "UNKNOWN")


class StatsSystemSerializer(Serializer):
    """Platform System Information."""

    name = CharField(required=False, read_only=True)
    release = CharField(required=False, read_only=True)


class StatsPlatformSerializer(Serializer):
    """Platform Information."""

    docker = BooleanField(read_only=True)
    machine = CharField(read_only=True)
    cores = IntegerField(read_only=True)
    system = StatsSystemSerializer(read_only=True)
    python_version = CharField(read_only=True)
    codex_version = CharField(read_only=True)


class StatsConfigSerializer(Serializer):
    """Config Information."""

    library_count = IntegerField(required=False, read_only=True)
    user_anonymous_count = IntegerField(required=False, read_only=True)
    user_registered_count = IntegerField(required=False, read_only=True)
    auth_group_count = IntegerField(required=False, read_only=True)
    # Only for api
    api_key = CharField(required=False, read_only=True)


class StatsSessionsSerializer(Serializer):
    """Session Settings."""

    top_group = CountDictField(required=False, read_only=True)
    order_by = CountDictField(required=False, read_only=True)
    dynamic_covers = CountDictField(required=False, read_only=True)
    finish_on_last_page = CountDictField(required=False, read_only=True)
    fit_to = CountDictField(required=False, read_only=True)
    reading_direction = CountDictField(required=False, read_only=True)


class StatsGroupSerializer(Serializer):
    """Group Counts."""

    publisher_count = IntegerField(required=False, read_only=True)
    imprint_count = IntegerField(required=False, read_only=True)
    series_count = IntegerField(required=False, read_only=True)
    volume_count = IntegerField(required=False, read_only=True)
    issue_count = IntegerField(required=False, read_only=True)
    folder_count = IntegerField(required=False, read_only=True)
    story_arc_count = IntegerField(required=False, read_only=True)


class StatsComicMetadataSerializer(Serializer):
    """Metadata Counts."""

    age_rating_count = IntegerField(required=False, read_only=True)
    character_count = IntegerField(required=False, read_only=True)
    contributor_count = IntegerField(required=False, read_only=True)
    contributor_person_count = IntegerField(required=False, read_only=True)
    contributor_role_count = IntegerField(required=False, read_only=True)
    country_count = IntegerField(required=False, read_only=True)
    genre_count = IntegerField(required=False, read_only=True)
    identifier_count = IntegerField(required=False, read_only=True)
    identifier_type_count = IntegerField(required=False, read_only=True)
    language_count = IntegerField(required=False, read_only=True)
    location_count = IntegerField(required=False, read_only=True)
    original_format_count = IntegerField(required=False, read_only=True)
    series_group_count = IntegerField(required=False, read_only=True)
    scan_info_count = IntegerField(required=False, read_only=True)
    story_arc_count = IntegerField(required=False)
    story_arc_number_count = IntegerField(required=False, read_only=True)
    tag_count = IntegerField(required=False, read_only=True)
    tagger_count = IntegerField(required=False, read_only=True)
    team_count = IntegerField(required=False, read_only=True)


class StatsSerializer(Serializer):
    """Admin Stats Tab."""

    platform = StatsPlatformSerializer(required=False)
    config = StatsConfigSerializer(required=False)
    sessions = StatsSessionsSerializer(required=False)
    groups = StatsGroupSerializer(required=False)
    file_types = CountDictField(required=False)
    metadata = StatsComicMetadataSerializer(required=False)


class AdminStatsRequestSerializer(Serializer):
    """Admin Stats Tab Request."""

    platform = SerializerChoicesField(
        serializer=StatsPlatformSerializer, required=False
    )
    config = SerializerChoicesField(serializer=StatsConfigSerializer, required=False)
    sessions = SerializerChoicesField(
        serializer=StatsSessionsSerializer, required=False
    )
    groups = SerializerChoicesField(serializer=StatsGroupSerializer, required=False)
    file_types = StringListMultipleChoiceField(choices=FILE_TYPES_CHOICES)
    metadata = SerializerChoicesField(
        serializer=StatsComicMetadataSerializer, required=False
    )


class APIKeySerializer(Serializer):
    """API Key."""

    api_key = CharField(source="name")
