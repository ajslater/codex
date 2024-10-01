"""Group Mtime Function."""

from logging import DEBUG, WARNING

from django.db.models.aggregates import Aggregate, Max
from django.db.models.functions import Greatest
from django.db.utils import OperationalError

from codex.logger.logging import get_logger
from codex.models.functions import JsonGroupArray
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.const import EPOCH_START, EPOCH_START_DATETIMEFIELD, NONE_DATETIMEFIELD

_FTS5_PREFIX = "fts5: "
LOG = get_logger(__name__)


class BrowserGroupMtimeView(BrowserFilterView):
    """Annotations that also filter."""

    def __init__(self, *args, **kwargs):
        """Initialize memoized values."""
        super().__init__(*args, **kwargs)
        self._is_bookmark_filtered: bool | None = None

    @property
    def is_bookmark_filtered(self):
        """Is bookmark filter in effect."""
        if self._is_bookmark_filtered is None:
            self._is_bookmark_filtered = bool(
                self.params.get("filters", {}).get("bookmark")
            )
        return self._is_bookmark_filtered

    def _handle_operational_error(self, err):
        msg = err.args[0] if err.args else ""
        if msg.startswith(_FTS5_PREFIX):
            level = DEBUG
            self.search_error = msg.removeprefix(_FTS5_PREFIX)
        else:
            level = WARNING
            msg = str(err)
        LOG.log(level, f"Query Error: {msg}")

    def get_max_bookmark_updated_at_aggregate(
        self, model, agg_func: type[Aggregate] = Max, default=NONE_DATETIMEFIELD
    ):
        """Get filtered maximum bookmark updated_at relation."""
        bm_rel = self._get_bm_rel(model)
        bm_filter = self._get_my_bookmark_filter(bm_rel)
        bmua_rel = f"{bm_rel}__updated_at"
        args = {"default": default, "filter": bm_filter}
        if agg_func is JsonGroupArray:
            args["distinct"] = True
        return agg_func(bmua_rel, **args)

    def get_group_mtime(self, model, group=None, pks=None, page_mtime=False):
        """Get a filtered mtime for browser pages and mtime checker."""
        qs = self.get_filtered_queryset(
            model,
            group=group,
            pks=pks,
            page_mtime=page_mtime,
            bookmark_filter=self.is_bookmark_filtered,
        )
        mua = Max("updated_at", default=EPOCH_START_DATETIMEFIELD)
        mbua = self.get_max_bookmark_updated_at_aggregate(
            model, default=EPOCH_START_DATETIMEFIELD
        )

        try:
            qs = qs.annotate(max=Greatest(mua, mbua))
            # Forcing inner joins makes search work
            # Can't run demote_joins on aggregate.
            qs = self.force_inner_joins(qs)
            first = qs.first()
            mtime = first.max if first else EPOCH_START
        except OperationalError as exc:
            self._handle_operational_error(exc)
            mtime = None
        if mtime == NotImplemented:
            mtime = None
        return mtime
