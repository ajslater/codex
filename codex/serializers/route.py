"""Vue Route Serializer."""

from dataclasses import asdict
from typing import override

from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import Serializer

from codex.group import Group, group_value
from codex.serializers.fields.group import BrowserRouteGroupField
from codex.serializers.fields.sanitized import SanitizedCharField
from codex.views.util import Route


def _collection_for_group(group) -> str:
    """Map a group value (collection or char) to its v4 collection (root → publishers)."""
    value = group_value(group)
    return Group.PUBLISHER.collection if value == Group.ROOT else value


def _parent_ids_for(pks: str) -> list[int]:
    """Parse the legacy comma ``pks`` string into a v4 parent-id list (drops 0)."""
    if not pks or pks == "0":
        return []
    return [int(pk) for pk in pks.split(",") if pk not in {"", "0"}]


class SimpleRouteSerializer(Serializer):
    """A an abbreviated vue route for the browser."""

    group = BrowserRouteGroupField()
    pks = CharField()

    @override
    def to_representation(self, instance) -> dict:
        """
        Emit both dialects during the migration.

        The legacy ``group``/``pks`` keys are kept for the current
        frontend; ``collection``/``parentIds`` are added for the v4
        frontend. Sequences are still accepted for ``pks``.
        """
        instance = asdict(instance) if isinstance(instance, Route) else dict(instance)
        pks = instance["pks"]
        if not pks:
            instance["pks"] = "0"
        elif not isinstance(pks, str):
            instance["pks"] = ",".join(str(pk) for pk in sorted(pks))
        data = super().to_representation(instance)
        data["collection"] = _collection_for_group(instance.get("group"))
        data["parent_ids"] = _parent_ids_for(instance["pks"])
        return data

    @override
    def to_internal_value(self, data) -> dict:
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
