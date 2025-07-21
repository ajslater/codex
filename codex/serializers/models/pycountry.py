"""Pycountry Model Serializers."""

from codex.models import (
    Country,
    Language,
)
from codex.serializers.fields.browser import CountryField, LanguageField
from codex.serializers.models.named import NamedModelSerializer


class CountrySerializer(NamedModelSerializer):
    """Pycountry serializer for country field."""

    name = CountryField(read_only=True)

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Country


class LanguageSerializer(NamedModelSerializer):
    """Pycountry serializer for language field."""

    name = LanguageField(read_only=True)

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Language
