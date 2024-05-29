"""Unused OPDS v2 Serializers."""

from rest_framework.fields import CharField, DateTimeField, DecimalField, IntegerField
from rest_framework.serializers import ChoiceField, Serializer

from codex.serializers.opds.v2 import OPDS2LinkListField


class RecursiveField(Serializer):
    """A recursive field type.

    There is a more comprehensive solution at
    https://pypi.org/project/djangorestframework-recursive/
    """

    def to_representation(self, instance):
        """Represent with own class."""
        parent = self.parent
        # Should not be ignored but is currently unused
        serializer = parent.parent.__class__(instance, context=self.context)  # type: ignore
        return serializer.data


class OPDS2PriceSerializer(Serializer):
    """Prices.

    https://drafts.opds.io/schema/properties.schema.json
    """

    value = DecimalField(read_only=True, max_digits=10, decimal_places=2)
    # by schema this should be a choices for allowed currencies.
    currency = CharField(read_only=True, max_length=3)


class OPDS2HoldsSerializer(Serializer):
    """Holds.

    https://drafts.opds.io/schema/properties.schema.json
    """

    total = IntegerField(read_only=True)
    position = IntegerField(read_only=True)


class OPDS2CopiesSerializer(Serializer):
    """Copies.

    https://drafts.opds.io/schema/properties.schema.json
    """

    total = IntegerField(read_only=True)
    available = IntegerField(read_only=True)


class OPDS2AcquisitionObjectSerializer(Serializer):
    """Acquisition Object.

    https://drafts.opds.io/schema/acquisition-object.schema.json
    """

    type = CharField(read_only=True)
    child = RecursiveField(many=True, required=False)


class OPDS2ProfileSerializer(Serializer):
    """Profile.

    https://drafts.opds.io/schema/profile.schema.json
    """

    name = CharField(read_only=True)
    email = CharField(read_only=True)
    links = OPDS2LinkListField(read_only=True, required=False)
    loans = OPDS2CopiesSerializer(read_only=True)
    holds = OPDS2HoldsSerializer(read_only=True)


class OPDS2AvailabilitySerializer(Serializer):
    """Availability.

    https://drafts.opds.io/schema/properties.schema.json
    """

    CHOICES = ("available", "unavailable", "reserved", "ready")

    state = ChoiceField(
        choices=CHOICES,
        read_only=True,
    )
    since = DateTimeField(read_only=True, required=False)
    until = DateTimeField(read_only=True, required=False)
