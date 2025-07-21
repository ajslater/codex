"""Browser Settings Filter Serializers."""

from rest_framework.serializers import ListField, Serializer

from codex.serializers.fields import (
    VuetifyBooleanField,
    VuetifyDecadeField,
    VuetifyDecimalField,
    VuetifyIntegerField,
)
from codex.serializers.fields.browser import BookmarkFilterField


class BrowserSettingsFilterInputSerializer(Serializer):
    """Filter values for settings."""

    bookmark = BookmarkFilterField(required=False)
    # Dynamic filters
    age_rating = ListField(child=VuetifyIntegerField(), required=False)
    characters = ListField(child=VuetifyIntegerField(), required=False)
    country = ListField(child=VuetifyIntegerField(), required=False)
    credits = ListField(child=VuetifyIntegerField(), required=False)
    critical_rating = ListField(
        child=VuetifyDecimalField(max_digits=5, decimal_places=2), required=False
    )
    decade = ListField(child=VuetifyDecadeField(), required=False)
    file_type = ListField(child=VuetifyIntegerField(), required=False)
    genres = ListField(child=VuetifyIntegerField(), required=False)
    identifier_source = ListField(child=VuetifyIntegerField(), required=False)
    language = ListField(child=VuetifyIntegerField(), required=False)
    locations = ListField(child=VuetifyIntegerField(), required=False)
    monochrome = ListField(child=VuetifyBooleanField(), required=False)
    original_format = ListField(child=VuetifyIntegerField(), required=False)
    reading_direction = ListField(child=VuetifyIntegerField(), required=False)
    series_groups = ListField(child=VuetifyIntegerField(), required=False)
    stories = ListField(child=VuetifyIntegerField(), required=False)
    story_arcs = ListField(child=VuetifyIntegerField(), required=False)
    tagger = ListField(child=VuetifyIntegerField(), required=False)
    tags = ListField(child=VuetifyIntegerField(), required=False)
    teams = ListField(child=VuetifyIntegerField(), required=False)
    universes = ListField(child=VuetifyIntegerField(), required=False)
    year = ListField(child=VuetifyIntegerField(), required=False)
