"""Serializer mixins."""

from typing import TYPE_CHECKING

from rest_framework.serializers import (
    BooleanField,
    DecimalField,
    IntegerField,
    ListField,
    SerializerMetaclass,
    SerializerMethodField,
)

from codex.serializers.fields.collection import BrowseCollectionField
from codex.util import max_none
from codex.views.const import EPOCH_START

if TYPE_CHECKING:
    from datetime import datetime


class BrowserAggregateSerializerMixin(metaclass=SerializerMetaclass):
    """Mixin for browser, opds & metadata serializers."""

    # Wire field ``collection``; the value comes from the ``nav_collection``
    # annotation (an internal alias the OPDS entry path also reads — it
    # can't be named ``collection`` without colliding with WatchedPath's
    # real ``collection`` field).
    collection = BrowseCollectionField(source="nav_collection", read_only=True)
    ids = ListField(child=IntegerField(), read_only=True)

    # Aggregate Annotations
    child_count = IntegerField(read_only=True)
    mtime = SerializerMethodField(read_only=True)

    # Bookmark annotations
    page = IntegerField(read_only=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(
        max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False
    )

    def get_mtime(self, obj) -> int:
        """Compute the card mtime from the row's updated_at + bookmark."""
        # ``updated_at_max`` is Max(updated_at) on the row's own column — the
        # collection's own timestamp (kept fresh by TimestampUpdater) or the
        # comic's own — folded with the per-user bookmark updated_at so a read
        # also bumps the card. When the primary sort is bookmark_updated_at
        # with Max, that order annotation is the same value; otherwise
        # ``annotate_bookmarks`` provides the Max under its own alias.
        mtime: datetime | None = getattr(obj, "updated_at_max", None) or EPOCH_START
        bmua_is_max = bool(getattr(self.context.get("view"), "bmua_is_max", False))  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
        bookmark_updated_at = (
            obj.bookmark_updated_at
            if bmua_is_max
            else getattr(obj, "bookmark_updated_at_max", None)
        )
        mtime = max_none(mtime, bookmark_updated_at, EPOCH_START)
        if mtime is None:
            return 0
        return int(mtime.timestamp() * 1000)
