"""Serializer mixins."""

from datetime import UTC, datetime

from loguru import logger
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

    @staticmethod
    def _get_max_updated_at(mtime, updated_ats) -> datetime:
        """Fold a JSON-array of ISO timestamps into a running max."""
        for dt_str in updated_ats:
            if not dt_str:
                continue
            try:
                # ``fromisoformat`` accepts the SQLite GROUP_CONCAT
                # output shape (``2024-01-15 10:30:45.123456``) since
                # Python 3.11 and is ~20x faster than ``strptime`` —
                # measurable savings on browser-list responses where
                # this loop runs ~50 cards x ~50 timestamps.
                dt = datetime.fromisoformat(dt_str).replace(tzinfo=UTC)
            except ValueError:
                logger.warning(
                    f"computing collection mtime: {dt_str} is not a valid datetime string."
                )
                continue
            mtime = max(dt, mtime)
        return mtime

    def get_mtime(self, obj) -> int:
        """Compute the card mtime from the row's updated_at + bookmark."""
        # ``updated_at_max`` is Max(updated_at) on the row's own column — the
        # collection's own timestamp (kept fresh by TimestampUpdater) or the
        # comic's own — folded with the per-user bookmark updated_at so a read
        # also bumps the card.
        mtime: datetime | None = getattr(obj, "updated_at_max", None) or EPOCH_START
        bmua_is_max = bool(getattr(self.context.get("view"), "bmua_is_max", False))  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
        if bmua_is_max:
            mtime = max_none(mtime, obj.bookmark_updated_at, EPOCH_START)
        else:
            mtime = self._get_max_updated_at(mtime, obj.bookmark_updated_ats)
        if mtime is None:
            return 0
        return int(mtime.timestamp() * 1000)
