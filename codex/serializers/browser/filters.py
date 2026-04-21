"""Browser Settings Filter Serializers."""

from rest_framework.serializers import Serializer

from codex.serializers.fields import (
    VuetifyBooleanField,
    VuetifyDecadeField,
    VuetifyDecimalField,
)
from codex.serializers.fields.browser import BookmarkFilterField
from codex.serializers.fields.vuetify import (
    VuetifyFileTypeChoiceField,
    VuetifyListField,
    VuetifyReadingDirectionChoiceField,
)


class BrowserSettingsFilterInputSerializer(Serializer):
    """Filter values for settings."""

    bookmark = BookmarkFilterField(required=False)
    # Dynamic filters
    age_rating = VuetifyListField()
    characters = VuetifyListField()
    country = VuetifyListField()
    credits = VuetifyListField()
    critical_rating = VuetifyListField(
        child=VuetifyDecimalField(max_digits=5, decimal_places=2)
    )
    decade = VuetifyListField(child=VuetifyDecadeField)
    file_type = VuetifyListField(child=VuetifyFileTypeChoiceField)
    genres = VuetifyListField()
    identifier_source = VuetifyListField()
    language = VuetifyListField()
    locations = VuetifyListField()
    metron_age_rating = VuetifyListField()
    monochrome = VuetifyListField(child=VuetifyBooleanField)
    original_format = VuetifyListField()
    reading_direction = VuetifyListField(child=VuetifyReadingDirectionChoiceField)
    series_groups = VuetifyListField()
    stories = VuetifyListField()
    story_arcs = VuetifyListField()
    tagger = VuetifyListField()
    tags = VuetifyListField()
    teams = VuetifyListField()
    universes = VuetifyListField()
    year = VuetifyListField()
