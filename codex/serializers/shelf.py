"""Shelf serializers."""

from typing import override

from rest_framework.fields import CharField, DictField, IntegerField, ListField
from rest_framework.serializers import Serializer, ValidationError

from codex.choices.limits import MAX_NAME_LEN
from codex.models.shelf import SHELF_COLLECTION_MODELS


class ShelfNameSerializer(Serializer):
    """Input for creating or renaming a shelf."""

    name = CharField(max_length=MAX_NAME_LEN, trim_whitespace=True)


class _ShelfTargetsField(DictField):
    """``{collection: [target_id, ...]}`` limited to the shelvable collections."""

    child = ListField(child=IntegerField(min_value=1), allow_empty=True)

    @override
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if unknown := sorted(set(value) - set(SHELF_COLLECTION_MODELS)):
            reason = f"Unknown shelf collection(s): {', '.join(unknown)}."
            raise ValidationError(reason)
        return value


class ShelfItemsSerializer(Serializer):
    """Input for adding targets to and removing targets from a shelf."""

    add = _ShelfTargetsField(required=False)
    remove = _ShelfTargetsField(required=False)
