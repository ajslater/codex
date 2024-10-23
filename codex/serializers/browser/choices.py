"""Browser Choices Serializer Map."""

from types import MappingProxyType

from rest_framework.fields import ListField, SerializerMethodField
from rest_framework.serializers import CharField, Serializer

from codex.serializers.browser.filters import BrowserSettingsFilterSerializer
from codex.serializers.fields import (
    VuetifyCharField,
    VuetifyIntegerField,
)
from codex.serializers.models.pycountry import CountrySerializer, LanguageSerializer


class BrowserChoicesCharPkSerializer(Serializer):
    """Named Model Serializer."""

    pk = VuetifyCharField(read_only=True)
    name = CharField(read_only=True)


class BrowserChoicesIntegerPkSerializer(BrowserChoicesCharPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = VuetifyIntegerField(read_only=True)


_CHOICES_NAME_SERIALIZER_MAP = MappingProxyType(
    {
        "bookmark": BrowserChoicesCharPkSerializer,
        "country": CountrySerializer,
        "language": LanguageSerializer,
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
            field: ListField = (  # type: ignore[reportAssignmentType]
                BrowserSettingsFilterSerializer().get_fields().get(field_name)
            )
            value = field.to_representation(choices)
        else:
            value = BrowserChoicesIntegerPkSerializer(choices, many=True).data
        return value
