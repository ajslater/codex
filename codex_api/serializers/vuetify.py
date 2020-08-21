"""Vuetify Choice Serializers."""
from rest_framework.serializers import CharField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import Serializer


class VueChoiceSerializer(Serializer):
    """Vuetify choice format."""

    text = CharField(read_only=True)

    class Meta:
        """Abstract class."""

        abstract = True


class VueStringChoiceSerializer(VueChoiceSerializer):
    """Vuetify string choice format."""

    value = CharField(read_only=True)


class VueIntChoiceSerializer(VueChoiceSerializer):
    """Vuetify int choice format."""

    value = IntegerField(read_only=True)
