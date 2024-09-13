"""Group Mtime Function."""

from logging import DEBUG, WARNING

from django.db.models.aggregates import Max
from django.db.models.functions import Coalesce, Greatest
from django.db.utils import OperationalError

from codex.logger.logging import get_logger
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.const import (
    EPOCH_START_DATETIMEFIELD,
)

_FTS5_PREFIX = "fts5: "
LOG = get_logger(__name__)


class BrowserGroupMtimeView(BrowserFilterView):
    """Annotations that also filter."""

    def _handle_operational_error(self, err):
        msg = err.args[0] if err.args else ""
        if msg.startswith(_FTS5_PREFIX):
            level = DEBUG
            self.search_error = msg.removeprefix(_FTS5_PREFIX)
        else:
            level = WARNING
            msg = str(err)
        LOG.log(level, f"Query Error: {msg}")

    def get_group_mtime(self, model, group=None, pks=None, page_mtime=False):
        """Get a filtered mtime for browser pages and mtime checker."""
        qs = self.get_filtered_queryset(
            model,
            group=group,
            pks=pks,
            bookmark_filter=self.is_bookmark_filtered,
            page_mtime=page_mtime,
        )
        qs = qs.annotate(max_updated_at=Max("updated_at"))

        if self.is_bookmark_filtered:
            bm_rel, bm_filter = self.get_bookmark_rel_and_filter(model)
            qs = qs.filter(bm_filter)
            ua_rel = bm_rel + "__updated_at"
            mbua = Max(ua_rel)
        else:
            mbua = EPOCH_START_DATETIMEFIELD
        qs = qs.annotate(max_bookmark_updated_at=mbua)

        try:
            mtime = qs.aggregate(
                max=Greatest(
                    Coalesce("max_bookmark_updated_at", EPOCH_START_DATETIMEFIELD),
                    "max_updated_at",
                )
            )["max"]
        except OperationalError as exc:
            self._handle_operational_error(exc)
            mtime = None
        if mtime == NotImplemented:
            mtime = None
        return mtime
