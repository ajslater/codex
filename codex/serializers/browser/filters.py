"""Browser Settings Filter Serializers."""

from rest_framework.serializers import (
    BooleanField,
    ChoiceField,
    Serializer,
)

from codex.serializers.choices import CHOICES
from codex.serializers.fields import (
    BooleanListField,
    CharListField,
    DecadeListField,
    FloatListField,
    IntListField,
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

    bookmark = ChoiceField(
        choices=tuple(CHOICES["bookmarkFilter"].keys()), required=False
    )
    # Dynamic filters
    age_rating = CharListField(allow_blank=True, required=False)
    characters = IntListField(required=False)
    community_rating = FloatListField(required=False)
    country = CharListField(allow_blank=True, required=False)
    contributors = IntListField(required=False)
    critical_rating = FloatListField(required=False)
    decade = DecadeListField(required=False)
    file_type = CharListField(allow_blank=True, required=False)
    genres = IntListField(required=False)
    identifier_type = CharListField(allow_blank=True, required=False)
    language = CharListField(allow_blank=True, required=False)
    locations = IntListField()
    monochrome = BooleanListField(required=False)
    original_format = CharListField(required=False, allow_blank=True)
    reading_direction = CharListField(required=False)
    series_groups = IntListField(required=False)
    stories = IntListField(required=False)
    story_arcs = IntListField(required=False)
    tagger = CharListField(required=False)
    tags = IntListField(required=False)
    teams = IntListField(required=False)
    year = IntListField(required=False)
