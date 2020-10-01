"""Vuetify Choice Serializers."""
# TODO going away in api v2

from rest_framework.serializers import CharField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import Serializer


class VueChoiceSerializer(Serializer):
    """Vuetify choice format."""

    text = CharField(read_only=True)

    class Meta:
        """Abstract class."""

        abstract = True


class VueIntChoiceSerializer(VueChoiceSerializer):
    """Vuetify int choice format."""

    value = IntegerField(read_only=True)
