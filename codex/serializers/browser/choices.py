"""Browser Choices Serializer Map."""

from types import MappingProxyType

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    FloatField,
    IntegerField,
    Serializer,
)

from codex.serializers.browser.filters import (
    BooleanListField,
    BrowserSettingsFilterSerializer,
    CharListField,
    DecadeListField,
    FloatListField,
    IntListField,
)


class BrowserChoicesCharPkSerializer(Serializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

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

_BSFS = BrowserSettingsFilterSerializer
CHOICES_SERIALIZER_CLASS_MAP = MappingProxyType(
    {
        name: _CHOICES_TYPE_SERIALIZER_MAP[field.__class__]
        for name, field in _BSFS().fields.items()  # type: ignore
    }
)
