"""Vuetify Choice Serializers."""
import pycountry

from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import Serializer
from rest_framework.serializers import SerializerMethodField
from rest_framework.serializers import URLField


# TODO after edit works. Some of these may never be used.
#      Boolean, Char, Decimal, URL


class VueChoiceSerializer(Serializer):
    """Vuetify choice format."""

    text = CharField(read_only=True)

    class Meta:
        """Abstract class."""

        abstract = True


class VueCharChoiceSerializer(VueChoiceSerializer):
    """Vuetify string choice format."""

    value = CharField(read_only=True)


class VueIntChoiceSerializer(VueChoiceSerializer):
    """Vuetify int choice format."""

    value = IntegerField(read_only=True)


class VueDecimalChoiceSerializer(VueChoiceSerializer):
    """Vuetify decimal choice format."""

    value = DecimalField(max_digits=5, decimal_places=2, read_only=True)


class VueBooleanChoiceSerializer(VueChoiceSerializer):
    """Vuetify bool choice format."""

    value = BooleanField(read_only=True)


class VueURLChoiceSerializer(VueChoiceSerializer):
    """Vuetify URL choice format."""

    value = URLField(read_only=True)


class VueMethodChoiceSerializer(Serializer):
    """Create the text in the choice with a Method."""

    value = SerializerMethodField()
    text = SerializerMethodField()

    class Meta:
        """Abstract Class."""

        abstract = True


class VuePyCountryChoiceSerializer(VueMethodChoiceSerializer):
    """Abstract class for looking up pycounty texts from value."""

    class Meta:
        """Abstract Class."""

        abstract = True

    def get_value(self, value):
        return value

    def get_text(self, value):
        """Long name from alpha2 pycountry module."""
        if not value:
            return None
        if len(value) == 2:
            # fix for https://github.com/flyingcircusio/pycountry/issues/41
            lookup_obj = self.LOOKUP_MODULE.get(alpha_2=value)
        else:
            lookup_obj = self.LOOKUP_MODULE.lookup(value)
        if lookup_obj:
            return lookup_obj.name


class VueCountryChoiceSerializer(VuePyCountryChoiceSerializer):
    """For pycountries."""

    LOOKUP_MODULE = pycountry.countries


class VueLanguageChoiceSerializer(VuePyCountryChoiceSerializer):
    """For pycountry languages."""

    LOOKUP_MODULE = pycountry.languages
