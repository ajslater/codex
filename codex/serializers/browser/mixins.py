"""Serializer mixins."""

from datetime import datetime, timezone
from itertools import chain

from loguru import logger
from rest_framework.serializers import (
    BooleanField,
    DecimalField,
    IntegerField,
    ListField,
    SerializerMetaclass,
    SerializerMethodField,
)

from codex.serializers.fields.group import BrowseGroupField
from codex.util import max_none
from codex.views.const import EPOCH_START


class BrowserAggregateSerializerMixin(metaclass=SerializerMetaclass):
    """Mixin for browser, opds & metadata serializers."""

    group = BrowseGroupField(read_only=True)
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
        """Because orm won't aggregate aggregates."""
        for dt_str in updated_ats:
            if not dt_str:
                continue
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                logger.warning(
                    f"computing group mtime: {dt_str} is not a valid datetime string."
                )
                continue
            mtime = max(dt, mtime)
        return mtime

    def get_mtime(self, obj) -> int:
        """Compute mtime from json array aggregates."""
        updated_ats = (
            obj.updated_ats
            if obj.bmua_is_max
            else chain(obj.updated_ats, obj.bookmark_updated_ats)
        )
        mtime = self._get_max_updated_at(EPOCH_START, updated_ats)
        if obj.bmua_is_max:
            mtime: datetime | None = max_none(
                mtime, obj.bookmark_updated_at, EPOCH_START
            )
        if mtime is None:
            return 0
        return int(mtime.timestamp() * 1000)
