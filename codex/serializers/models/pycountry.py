"""Pycountry Model Serializers."""

import pycountry
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import (
    SerializerMethodField,
)

from codex.models import (
    Country,
    Language,
)
from codex.serializers.models.named import NamedModelSerializer


class PyCountrySerializer(NamedModelSerializer):
    """PyCountry tag serializer to include long names.

    Takes a single string value and serializes the value to
    a pk attribute and a pycountry long name lookup of that value to
    the name.
    """

    LOOKUP_MODULE = pycountry.countries
    _ALPHA_2_LEN = 2

    name = SerializerMethodField()

    class Meta(NamedModelSerializer.Meta):
        """Abstract class."""

        abstract = True

    @classmethod
    def lookup_name(cls, lookup_module, obj):
        """Lookup the name with pycountry, just copy the key on fail."""
        name = obj.name
        if not name:
            return ""
        # fix for https://github.com/flyingcircusio/pycountry/issues/41
        lookup_obj = (
            lookup_module.get(alpha_2=name)
            if len(name) == cls._ALPHA_2_LEN
            else lookup_module.lookup(name)
        )
        # If lookup fails, return the key as the name
        return lookup_obj.name if lookup_obj else name

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, obj):
        """Lookup the name with pycountry, just copy the key on fail."""
        return self.lookup_name(self.LOOKUP_MODULE, obj)


class LanguageSerializer(PyCountrySerializer):
    """Pycountry serializer for language field."""

    LOOKUP_MODULE = pycountry.languages

    class Meta(PyCountrySerializer.Meta):
        """Configure model."""

        model = Language


class CountrySerializer(PyCountrySerializer):
    """Pycountry serializer for country field."""

    class Meta(PyCountrySerializer.Meta):
        """Configure model."""

        model = Country
