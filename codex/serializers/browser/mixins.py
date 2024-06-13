"""Serializer mixins."""

from datetime import datetime, timezone

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
    ListField,
    Serializer,
    SerializerMethodField,
)

from codex.logger.logging import get_logger
from codex.views.const import COMIC_GROUP, EPOCH_START

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
    bookmark_updated_at = DateTimeField(read_only=True, allow_null=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(
        max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False
    )

    def get_mtime(self, obj) -> int:
        """Compute mtime from json array aggregates."""
        mtime = EPOCH_START
        for dt_str in obj.updated_ats:
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

            if dt > mtime:
                mtime = dt

        if obj.group != COMIC_GROUP and (
            mbua := getattr(obj, "max_bookmark_updated_at", None)
        ):
            mtime = max(mtime, mbua)

        # print(obj.group, obj.pk, obj.name, obj.updated_ats, obj.max_bookmark_updated_at, "max:", mtime)
        return int(mtime.timestamp() * 1000)
