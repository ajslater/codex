"""Vue Route Serializer."""

from collections.abc import Iterable
from dataclasses import asdict
from typing import override

from rest_framework.fields import CharField, IntegerField
from rest_framework.serializers import Serializer

from codex.collection import Collection
from codex.serializers.fields.collection import BrowserRouteCollectionField
from codex.serializers.fields.sanitized import SanitizedCharField
from codex.views.util import Route


def _v4_collection(collection) -> str:
    """Map an engine collection value to its v4 collection (root → publishers)."""
    return (
        Collection.PUBLISHER.collection if collection == Collection.ROOT else collection
    )


def _parent_ids_for(pks) -> list[int]:
    """Normalize a ``pks`` tuple/list (or legacy comma string) to a v4 parent-id list (drops 0)."""
    if not pks:
        return []
    if isinstance(pks, str):
        pks = pks.split(",")
    if isinstance(pks, Iterable):
        return sorted({int(pk) for pk in pks if str(pk) not in {"", "0"}})
    return []


class SimpleRouteSerializer(Serializer):
    """
    An abbreviated vue route for the browser.

    Input and output both speak the ``collection``/``parentIds`` dialect
    (``pks`` is kept as the input parent-ids key; output emits ``parent_ids``).
    """

    collection = BrowserRouteCollectionField()
    pks = CharField()

    @override
    def to_representation(self, instance) -> dict:
        """Emit the v4 ``collection``/``parent_ids`` dialect (+ page/name)."""
        instance = asdict(instance) if isinstance(instance, Route) else dict(instance)
        data = {
            "collection": _v4_collection(instance.get("collection")),
            "parent_ids": _parent_ids_for(instance.get("pks")),
        }
        # ``page``/``name`` only exist on the full ``RouteSerializer``; emit
        # them through their declared fields so sanitization still applies.
        if (page_field := self.fields.get("page")) is not None:
            data["page"] = page_field.to_representation(instance.get("page", 1))
        if (name_field := self.fields.get("name")) is not None:
            data["name"] = name_field.to_representation(instance.get("name") or "")
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
