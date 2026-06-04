"""Collection Mtime Function."""

import hashlib
import json
from typing import TYPE_CHECKING

from django.core.cache import cache as _django_cache
from django.db.models.aggregates import Aggregate, Max
from django.db.models.functions import Greatest
from django.db.utils import OperationalError
from loguru import logger

from codex.models.functions import JsonGroupArray
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.const import EPOCH_START, EPOCH_START_DATETIMEFIELD, NONE_DATETIMEFIELD

if TYPE_CHECKING:
    from django.db.models import Q, Value

_FTS5_PREFIX = "fts5: "
_PAGE_MTIME_TTL_SECONDS = 5
_PAGE_MTIME_CACHE_MISS = object()
_PAGE_MTIME_NONE_SENTINEL = "none"


class BrowserCollectionMtimeView(BrowserFilterView):
    """Annotations that also filter."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize memoized values."""
        super().__init__(*args, **kwargs)
        self._is_bookmark_filtered: bool | None = None
        self._bmua_agg_cache: dict = {}

    @property
    def is_bookmark_filtered(self) -> bool:
        """Is bookmark filter in effect."""
        if self._is_bookmark_filtered is None:
            self._is_bookmark_filtered = bool(
                self.params.get("filters", {}).get("bookmark")
            )
        return self._is_bookmark_filtered

    def _handle_operational_error(self, err) -> None:
        msg = err.args[0] if err.args else ""
        if msg.startswith(_FTS5_PREFIX):
            level = "DEBUG"
            self.search_error = msg.removeprefix(_FTS5_PREFIX)
        else:
            level = "WARNING"
            msg = str(err)
        logger.log(level, f"Query Error: {msg}")
        # logger.exception(f"Query Error: {msg}") debug

    def get_max_bookmark_updated_at_aggregate(
        self, model, agg_func: type[Aggregate] = Max, default=NONE_DATETIMEFIELD
    ) -> Aggregate:
        """Get filtered maximum bookmark updated_at relation."""
        key = (model, agg_func, default)
        cached = self._bmua_agg_cache.get(key)
        if cached is not None:
            return cached

        bm_rel = self.get_bm_rel(model)
        bm_filter = self.get_my_bookmark_filter(bm_rel)
        bmua_rel = f"{bm_rel}__updated_at"
        kwargs: dict[str, bool | str | Value | Q] = {
            "default": default,
            "filter": bm_filter,
        }
        if agg_func is JsonGroupArray:
            kwargs["distinct"] = True
            kwargs["order_by"] = bmua_rel

        aggregate = agg_func(bmua_rel, **kwargs)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
        self._bmua_agg_cache[key] = aggregate
        return aggregate

    def _page_mtime_cache_key(self, model) -> str:
        """Stable key scoped to user + filter-affecting params."""
        user_id = self.request.user.pk if self.request.user.is_authenticated else 0
        collection = self.kwargs.get("collection", "r")
        pks = tuple(self.kwargs.get("pks") or (0,))
        page = self.kwargs.get("page", 1)
        filter_keys = ("filters", "search", "q", "order_by", "order_reverse")
        params_data = {k: self.params.get(k) for k in filter_keys}
        params_str = json.dumps(params_data, sort_keys=True, default=str)
        params_hash = hashlib.blake2s(params_str.encode(), digest_size=8).hexdigest()
        return (
            f"codex:page_mtime:{user_id}:{model.__name__}:"
            f"{collection}:{pks}:{page}:{params_hash}"
        )

    def get_collection_mtime(
        self, model, collection=None, pks=None, *, page_mtime=False
    ):
        """
        Get a filtered mtime for browser pages and mtime checker.

        When ``page_mtime`` is true this is called from the browse page
        response — the query is a filtered Max aggregate that runs even on
        cachalot misses (writes to Comic/Bookmark invalidate it). A short
        TTL cache absorbs concurrent recomputes within that window; real
        staleness is bounded by TTL + cachalot's signal-driven invalidation.
        """
        cache_key = self._page_mtime_cache_key(model) if page_mtime else ""
        if cache_key:
            cached = self._get_cached_page_mtime(cache_key)
            if cached is not _PAGE_MTIME_CACHE_MISS:
                return cached
        mtime = self._query_collection_mtime(
            model, collection, pks, page_mtime=page_mtime
        )
        if cache_key:
            self._store_page_mtime(cache_key, mtime)
        return mtime

    @staticmethod
    def _get_cached_page_mtime(cache_key: str):
        """Return the cached mtime (decoding the None sentinel) or MISS if absent."""
        cached = _django_cache.get(cache_key, _PAGE_MTIME_CACHE_MISS)
        if cached is _PAGE_MTIME_CACHE_MISS:
            return _PAGE_MTIME_CACHE_MISS
        return None if cached == _PAGE_MTIME_NONE_SENTINEL else cached

    @staticmethod
    def _store_page_mtime(cache_key: str, mtime) -> None:
        """Cache the mtime for the TTL window, encoding None via the sentinel."""
        stored = _PAGE_MTIME_NONE_SENTINEL if mtime is None else mtime
        _django_cache.set(cache_key, stored, _PAGE_MTIME_TTL_SECONDS)

    def _query_collection_mtime(self, model, collection, pks, *, page_mtime: bool):
        """Run the filtered Max aggregate; None on a (logged) query error."""
        qs = self.get_filtered_queryset(
            model,
            collection=collection,
            pks=pks,
            page_mtime=page_mtime,
            bookmark_filter=self.is_bookmark_filtered,
        )
        # Read the collection's own ``updated_at`` (kept fresh by
        # ``TimestampUpdater`` when a child comic or custom cover changes)
        # rather than re-aggregating ``comic__updated_at`` — drops the comic
        # join and matches the per-card mtime and how OPDS/reader read it.
        mua = Max("updated_at", default=EPOCH_START_DATETIMEFIELD)
        mbua = self.get_max_bookmark_updated_at_aggregate(
            model, default=EPOCH_START_DATETIMEFIELD
        )
        # Folding the linked ``CustomCover.updated_at`` into the
        # aggregate makes a cover upload (which never touches a Comic
        # row) bump the collection's reported mtime — without this, the
        # frontend's ``loadMtimes`` shortcut sees an unchanged value
        # after a COVERS broadcast and never triggers the page reload.
        # ``model.custom_cover`` is the (inherited) FK on every
        # ``BrowserCollectionModel`` subclass; ``Comic`` is the only model
        # we route through this view that lacks it.
        agg_terms = [mua, mbua]
        if any(f.name == "custom_cover" for f in model._meta.get_fields()):
            agg_terms.append(
                Max("custom_cover__updated_at", default=EPOCH_START_DATETIMEFIELD)
            )
        try:
            qs = qs.annotate(max=Greatest(*agg_terms))
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
