"""Vue Route Serializer."""

from dataclasses import asdict

from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import Serializer
from typing_extensions import override

from codex.serializers.fields.group import BrowserRouteGroupField
from codex.serializers.fields.sanitized import SanitizedCharField
from codex.views.util import Route


class SimpleRouteSerializer(Serializer):
    """A an abbreviated vue route for the browser."""

    group = BrowserRouteGroupField()
    pks = CharField()

    @override
    def to_representation(self, instance):
        """Allow submission of sequences instead of strings for pks."""
        instance = asdict(instance) if isinstance(instance, Route) else dict(instance)
        pks = instance["pks"]
        if not pks:
            instance["pks"] = "0"
        elif not isinstance(pks, str):
            instance["pks"] = ",".join(str(pk) for pk in sorted(pks))
        return super().to_representation(instance)

    @override
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


class RouteSerializer(SimpleRouteSerializer):
    """A vue route for the browser."""

    page = IntegerField()
    name = SanitizedCharField(allow_blank=True, required=False)
