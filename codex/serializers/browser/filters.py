"""Browser Settings Filter Serializers."""

from rest_framework.serializers import BooleanField, ListField, Serializer

from codex.serializers.fields import (
    BookmarkFilterField,
    VuetifyBooleanField,
    VuetifyCharField,
    VuetifyDecadeField,
    VuetifyFloatField,
    VuetifyIntegerField,
)


class BrowserFilterChoicesSerializer(Serializer):
    """All dynamic filters."""

    age_rating = BooleanField(read_only=True)
    community_rating = BooleanField(read_only=True)
    characters = BooleanField(read_only=True)
    country = BooleanField(read_only=True)
    critical_rating = BooleanField(read_only=True)
    contributors = BooleanField(read_only=True)
    decade = BooleanField(read_only=True)
    genres = BooleanField(read_only=True)
    file_type = BooleanField(read_only=True)
    identifier_type = BooleanField(read_only=True)
    monochrome = BooleanField(read_only=True)
    language = BooleanField(read_only=True)
    locations = BooleanField(read_only=True)
    original_format = BooleanField(read_only=True)
    reading_direction = BooleanField(read_only=True)
    series_groups = BooleanField(read_only=True)
    stories = BooleanField(read_only=True)
    story_arcs = BooleanField(read_only=True)
    tagger = BooleanField(read_only=True)
    tags = BooleanField(read_only=True)
    teams = BooleanField(read_only=True)
    year = BooleanField(read_only=True)


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = BookmarkFilterField(required=False)
    # Dynamic filters
    age_rating = ListField(child=VuetifyCharField(), required=False)
    characters = ListField(child=VuetifyIntegerField(), required=False)
    community_rating = ListField(child=VuetifyFloatField(), required=False)
    country = ListField(child=VuetifyIntegerField(), required=False)
    contributors = ListField(child=VuetifyIntegerField(), required=False)
    critical_rating = ListField(child=VuetifyFloatField(), required=False)
    decade = ListField(child=VuetifyDecadeField(), required=False)
    file_type = ListField(child=VuetifyCharField(), required=False)
    genres = ListField(child=VuetifyIntegerField(), required=False)
    identifier_type = ListField(child=VuetifyCharField(), required=False)
    language = ListField(child=VuetifyIntegerField(), required=False)
    locations = ListField(child=VuetifyIntegerField(), required=False)
    monochrome = ListField(child=VuetifyBooleanField(), required=False)
    original_format = ListField(child=VuetifyCharField(), required=False)
    reading_direction = ListField(child=VuetifyCharField(), required=False)
    series_groups = ListField(child=VuetifyIntegerField(), required=False)
    stories = ListField(child=VuetifyIntegerField(), required=False)
    story_arcs = ListField(child=VuetifyIntegerField(), required=False)
    tagger = ListField(child=VuetifyCharField(), required=False)
    tags = ListField(child=VuetifyIntegerField(), required=False)
    teams = ListField(child=VuetifyIntegerField(), required=False)
    year = ListField(child=VuetifyIntegerField(), required=False)
