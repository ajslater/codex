"""Vue Route Serializer."""

from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import Serializer

from codex.views.util import Route


class SimpleRouteSerializer(Serializer):
    """A an abbreviated vue route for the browser."""

    group = CharField()
    pks = CharField()

    def to_representation(self, instance):
        """Allow submission of sequences instead of strings for pks."""
        if isinstance(instance, Route):
            instance = instance.dict()
        pks = instance["pks"]
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
            if 0 in pks:  # type: ignore
                pks = ()
            instance["pks"] = tuple(pks)  # type: ignore
        except ValueError:
            instance["pks"] = ()
        return instance


class RouteSerializer(SimpleRouteSerializer):
    """A vue route for the browser."""

    page = IntegerField()
    name = CharField(allow_blank=True, required=False)
