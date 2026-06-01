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
    group: model for model, group in CLASS_CUSTOM_COVER_COLLECTION_MAP.items()
}
_GROUP_LABELS = {
    "publishers": "Publisher",
    "imprints": "Imprint",
    "series": "Series",
    "volumes": "Volume",
    "arcs": "Story Arc",
    "folders": "Folder",
}


class CustomCoverSerializer(BaseModelSerializer):
    """CustomCover list serializer for the admin tab."""

    group_label = SerializerMethodField()
    linked_group_pk = SerializerMethodField()
    linked_group_name = SerializerMethodField()
    size_bytes = SerializerMethodField()
    mtime = SerializerMethodField()
    path = CharField(read_only=True)
    pk = IntegerField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        """Specify model + fields."""

        model = CustomCover
        fields = (
            "pk",
            "group",
            "group_label",
            "linked_group_pk",
            "linked_group_name",
            "path",
            "mtime",
            "size_bytes",
        )
        read_only_fields = fields

    class JSONAPIMeta:
        """JSON:API resource_name for the v4 admin renderer."""

        resource_name = "custom-covers"

    @staticmethod
    def get_group_label(obj: CustomCover) -> str:
        """Human-readable group name."""
        return _GROUP_LABELS.get(obj.group, obj.group)

    @staticmethod
    def _linked(obj: CustomCover):
        model = _MODEL_BY_COLLECTION.get(obj.group)
        if model is None:
            return None
        return model.objects.filter(custom_cover_id=obj.pk).first()

    def get_linked_group_pk(self, obj: CustomCover) -> int | None:
        """First linked browser group's pk, if any."""
        linked = self._linked(obj)
        return None if linked is None else linked.pk

    def get_linked_group_name(self, obj: CustomCover) -> str | None:
        """Display name of the first linked group."""
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
