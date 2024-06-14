"""Browser Choices Serializer Map."""

from types import MappingProxyType

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    CharField,
    Serializer,
)
from rest_framework.utils.serializer_helpers import ReturnList

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

    def get_choices(self, obj) -> ReturnList:
        """Dynamic Serializer response by field type."""
        field_name = obj.get("field_name", "")
        choices = obj.get("choices", [])
        serializer_class = _CHOICES_NAME_SERIALIZER_MAP.get(field_name)
        value: ReturnList
        if serializer_class:
            value = serializer_class(choices, many=True).data  # type: ignore
        elif not serializer_class and field_name in _LIST_FIELDS:
            field = BrowserSettingsFilterSerializer().get_fields().get(field_name)  # type: ignore
            value = field.to_representation(choices)
        else:
            value = BrowserChoicesIntegerPkSerializer(choices, many=True).data  # type: ignore
        return value
