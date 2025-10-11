"""Browser Choices Serializer Map."""

from types import MappingProxyType

from rest_framework.fields import (
    BooleanField,
    CharField,
    ListField,
    SerializerMethodField,
)
from rest_framework.serializers import Serializer

from codex.serializers.fields import (
    VuetifyBooleanField,
    VuetifyCharField,
    VuetifyDecadeField,
    VuetifyDecimalField,
    VuetifyIntegerField,
)
from codex.serializers.fields.browser import BookmarkFilterField
from codex.serializers.fields.vuetify import (
    VuetifyFileTypeChoiceField,
    VuetifyReadingDirectionChoiceField,
)
from codex.serializers.models.pycountry import CountrySerializer, LanguageSerializer


class BrowserFilterChoicesSerializer(Serializer):
    """All dynamic filters."""

    age_rating = BooleanField(read_only=True)
    characters = BooleanField(read_only=True)
    country = BooleanField(read_only=True)
    critical_rating = BooleanField(read_only=True)
    credits = BooleanField(read_only=True)
    decade = BooleanField(read_only=True)
    genres = BooleanField(read_only=True)
    file_type = BooleanField(read_only=True)
    identifier_source = BooleanField(read_only=True)
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
    universes = BooleanField(read_only=True)
    year = BooleanField(read_only=True)


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = BookmarkFilterField(required=False, read_only=True)
    # Dynamic filters
    age_rating = ListField(child=VuetifyCharField(), required=False, read_only=True)
    characters = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    country = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    credits = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    critical_rating = ListField(
        child=VuetifyDecimalField(max_digits=5, decimal_places=2),
        required=False,
        read_only=True,
    )
    decade = ListField(child=VuetifyDecadeField(), required=False, read_only=True)
    file_type = ListField(
        child=VuetifyFileTypeChoiceField(), required=False, read_only=True
    )
    genres = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    identifier_source = ListField(
        child=VuetifyCharField(), required=False, read_only=True
    )
    language = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    locations = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    monochrome = ListField(child=VuetifyBooleanField(), required=False, read_only=True)
    original_format = ListField(
        child=VuetifyCharField(), required=False, read_only=True
    )
    reading_direction = ListField(
        child=VuetifyReadingDirectionChoiceField(), required=False, read_only=True
    )
    series_groups = ListField(
        child=VuetifyIntegerField(), required=False, read_only=True
    )
    stories = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    story_arcs = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    tagger = ListField(child=VuetifyCharField(), required=False, read_only=True)
    tags = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    teams = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    universes = ListField(child=VuetifyIntegerField(), required=False, read_only=True)
    year = ListField(child=VuetifyIntegerField(), required=False, read_only=True)


class BrowserChoicesIntegerPkSerializer(Serializer):
    """Named Model Serializer."""

    pk = VuetifyIntegerField(read_only=True)
    name = CharField(read_only=True)


class BrowserChoicesUniversePkSerializer(Serializer):
    """Universes Only."""

    designation = CharField(read_only=True)


class BrowserChoicesCharPkSerializer(BrowserChoicesIntegerPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = VuetifyCharField(read_only=True)


class BrowserChoicesDecimalPkSerializer(BrowserChoicesIntegerPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = VuetifyDecimalField(max_digits=5, decimal_places=2, read_only=True)


_CHOICES_NAME_SERIALIZER_MAP = MappingProxyType(
    {
        "bookmark": BrowserChoicesCharPkSerializer,
        "country": CountrySerializer,
        "critical_rating": BrowserChoicesDecimalPkSerializer,
        "file_type": BrowserChoicesCharPkSerializer,
        "language": LanguageSerializer,
        "universe": BrowserChoicesUniversePkSerializer,
    }
)
_LIST_FIELDS = frozenset({"decade", "monochrome", "reading_direction", "year"})


class BrowserChoicesFilterSerializer(Serializer):
    """Dynamic Serializer response by field type."""

    choices = SerializerMethodField(read_only=True)

    def get_choices(self, obj) -> list:
        """Dynamic Serializer response by field type."""
        field_name = obj.get("field_name", "")
        choices = obj.get("choices", [])
        serializer_class = _CHOICES_NAME_SERIALIZER_MAP.get(field_name)
        value: list
        if serializer_class:
            value = serializer_class(choices, many=True).data
        elif not serializer_class and field_name in _LIST_FIELDS:
            field = BrowserSettingsFilterSerializer().get_fields().get(field_name)
            value = field.to_representation(choices)  #  pyright: ignore[reportOptionalMemberAccess],# ty: ignore[possibly-missing-attribute]
        else:
            value = BrowserChoicesIntegerPkSerializer(choices, many=True).data
        return value
