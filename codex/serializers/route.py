"""Vue Route Serializer."""

from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import Serializer


class RouteSerializer(Serializer):
    """A vue route for the browser."""

    group = CharField()
    pks = CharField()
    page = IntegerField()
    name = CharField(required=False)

    def to_representation(self, instance):
        """Allow submission of sequences instead of strings for pks."""
        pks = instance.get("pks")
        if not pks:
            instance["pks"] = "0"
        elif not isinstance(pks, str):
            instance["pks"] = ",".join(str(pk) for pk in sorted(pks))
        return super().to_representation(instance)

    def to_internal_value(self, data):
        """Convert pk strings to tuples."""
        instance = super().to_internal_value(data)
        try:
            pks = instance.get("pks")
            if isinstance(pks, str):
                pks = tuple(sorted(int(pk) for pk in pks.split(",")))
            if 0 in pks:
                pks = ()
            instance["pks"] = tuple(pks)
        except ValueError:
            instance["pks"] = ()
        return instance
