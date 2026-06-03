"""Custom cover admin serializers."""

from __future__ import annotations

from pathlib import Path

from rest_framework.serializers import (
    CharField,
    IntegerField,
    SerializerMethodField,
)

from codex.librarian.scribe.importer.const import CLASS_CUSTOM_COVER_COLLECTION_MAP
from codex.models import CustomCover
from codex.serializers.models.base import BaseModelSerializer

_MODEL_BY_COLLECTION = {
    collection: model for model, collection in CLASS_CUSTOM_COVER_COLLECTION_MAP.items()
}
_COLLECTION_LABELS = {
    "publishers": "Publisher",
    "imprints": "Imprint",
    "series": "Series",
    "volumes": "Volume",
    "arcs": "Story Arc",
    "folders": "Folder",
}


class CustomCoverSerializer(BaseModelSerializer):
    """CustomCover list serializer for the admin tab."""

    collection = CharField(read_only=True)
    collection_label = SerializerMethodField()
    linked_collection_pk = SerializerMethodField()
    linked_collection_name = SerializerMethodField()
    size_bytes = SerializerMethodField()
    mtime = SerializerMethodField()
    path = CharField(read_only=True)
    pk = IntegerField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        """Specify model + fields."""

        model = CustomCover
        fields = (
            "pk",
            "collection",
            "collection_label",
            "linked_collection_pk",
            "linked_collection_name",
            "path",
            "mtime",
            "size_bytes",
        )
        read_only_fields = fields

    class JSONAPIMeta:
        """JSON:API resource_name for the v4 admin renderer."""

        resource_name = "custom-covers"

    @staticmethod
    def get_collection_label(obj: CustomCover) -> str:
        """Human-readable collection name."""
        return _COLLECTION_LABELS.get(obj.collection, obj.collection)

    @staticmethod
    def _linked(obj: CustomCover):
        model = _MODEL_BY_COLLECTION.get(obj.collection)
        if model is None:
            return None
        return model.objects.filter(custom_cover_id=obj.pk).first()

    def get_linked_collection_pk(self, obj: CustomCover) -> int | None:
        """First linked browser collection's pk, if any."""
        linked = self._linked(obj)
        return None if linked is None else linked.pk

    def get_linked_collection_name(self, obj: CustomCover) -> str | None:
        """Display name of the first linked collection."""
        linked = self._linked(obj)
        if linked is None:
            return None
        return str(getattr(linked, "name", None) or repr(linked))

    @staticmethod
    def _stat_entry(obj: CustomCover, idx: int):
        stat = obj.stat
        if not stat or idx >= len(stat):
            return None
        return stat[idx]

    def get_size_bytes(self, obj: CustomCover) -> int | None:
        """File size from the saved stat tuple."""
        size = self._stat_entry(obj, 6)
        if size is None and obj.path:
            try:
                return Path(obj.path).stat().st_size
            except OSError:
                return None
        return int(size) if size is not None else None

    def get_mtime(self, obj: CustomCover) -> float | None:
        """File mtime from the saved stat tuple."""
        return self._stat_entry(obj, 8)
