"""Serializer mixins."""

from datetime import datetime, timezone
from itertools import chain

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    ListField,
    Serializer,
    SerializerMethodField,
)

from codex.logger.logging import get_logger
from codex.util import max_none
from codex.views.const import EPOCH_START

LOG = get_logger(__name__)


class BrowserAggregateSerializerMixin(Serializer):
    """Mixin for browser, opds & metadata serializers."""

    group = CharField(read_only=True, max_length=1)
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
                LOG.warning(
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
            mtime: datetime = max_none(mtime, obj.bookmark_updated_at, EPOCH_START)  # type: ignore
        return int(mtime.timestamp() * 1000)
