"""Browser Choices Serializer Map."""

from types import MappingProxyType

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    FloatField,
    IntegerField,
    Serializer,
)
from rest_framework.utils.serializer_helpers import ReturnList

from codex.serializers.browser.filters import BrowserSettingsFilterSerializer
from codex.serializers.fields import (
    BooleanListField,
    CharListField,
    DecadeListField,
    FloatListField,
    IntListField,
)
from codex.serializers.models.pycountry import CountrySerializer, LanguageSerializer


class BrowserChoicesCharPkSerializer(Serializer):
    """Named Model Serializer."""

    pk = CharField(read_only=True)
    name = CharField(read_only=True)


class BrowserChoicesBoolPkSerializer(BrowserChoicesCharPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = BooleanField(read_only=True)


class BrowserChoicesIntPkSerializer(BrowserChoicesCharPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = IntegerField(read_only=True)


class BrowserChoicesFloatPkSerializer(BrowserChoicesCharPkSerializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = FloatField(read_only=True)


_CHOICES_TYPE_SERIALIZER_MAP = MappingProxyType(
    {
        BooleanListField: BrowserChoicesBoolPkSerializer,
        CharListField: BrowserChoicesCharPkSerializer,
        ChoiceField: BrowserChoicesCharPkSerializer,
        DecadeListField: BrowserChoicesIntPkSerializer,
        FloatListField: BrowserChoicesFloatPkSerializer,
        IntListField: BrowserChoicesIntPkSerializer,
    }
)
_CHOICES_NAME_SERIALIZER_MAP = MappingProxyType(
    {"country": CountrySerializer, "language": LanguageSerializer}
)


def _create_choices_field_serializer_map():
    serializer_map = {}
    for name, field in BrowserSettingsFilterSerializer().fields.items():  # type: ignore
        serializer_class = _CHOICES_NAME_SERIALIZER_MAP.get(name)
        if not serializer_class:
            serializer_class = _CHOICES_TYPE_SERIALIZER_MAP[field.__class__]
        serializer_map[name] = serializer_class

    return MappingProxyType(serializer_map)


_CHOICES_SERIALIZER_CLASS_MAP = _create_choices_field_serializer_map()


class BrowserChoicesFilterSerializer(Serializer):
    """Dynamic Serializer response by field type."""

    choices = SerializerMethodField(read_only=True)

    def get_choices(self, obj) -> ReturnList:
        """Dynamic Serializer response by field type."""
        key = obj.get("field_name", "")
        choices = obj.get("choices", [])
        serializer_class = _CHOICES_SERIALIZER_CLASS_MAP.get(
            key, BrowserChoicesCharPkSerializer
        )
        serializer = serializer_class(choices, many=True)
        return serializer.data  # type: ignore
