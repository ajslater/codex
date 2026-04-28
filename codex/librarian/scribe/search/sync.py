"""Search Index update."""

from datetime import datetime
from math import floor
from time import monotonic
from types import MappingProxyType
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.db.models.aggregates import Max
from django.db.models.expressions import F, Value
from django.db.models.functions import Concat
from django.db.models.query import QuerySet
from humanize import intcomma, naturaldelta

from codex.librarian.memory import get_mem_limit
from codex.librarian.scribe.search.const import COMICFTS_UPDATE_FIELDS
from codex.librarian.scribe.search.prepare import SearchEntryPrepare
from codex.librarian.scribe.search.remove import SearchIndexerRemove
from codex.librarian.scribe.search.status import (
    SEARCH_INDEX_STATII,
    SearchIndexCleanStatus,
    SearchIndexClearStatus,
    SearchIndexSyncCreateStatus,
    SearchIndexSyncUpdateStatus,
)
from codex.models import Comic
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat
from codex.settings import IMPORTER_SEARCH_SYNC_BATCH_MEMORY_RATIO

if TYPE_CHECKING:
    from codex.librarian.status import Status

_MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
_ALL_FTS_COMIC_IDS_QUERY = Q(pk__in=ComicFTS.objects.values_list("comic_id", flat=True))
_SIMPLE_FTS_FIELDS = (
    # Group Fks
    "publisher",
    "imprint",
    "series",
    # Fks
    "country",
    "original_format",
    "language",
    "scan_info",
    "tagger",
)
_SIMPLE_FTS_ANNOTATIONS = MappingProxyType(
    {
        **{f"fts_{rel}": F(f"{rel}__name") for rel in _SIMPLE_FTS_FIELDS},
        # The Comic.age_rating FK powers two FTS columns:
        #   age_rating_tagged  ← AgeRating.name                (raw tagged string)
        #   age_rating_metron  ← AgeRating.metron.name         (canonical value)
        # The second traverses the AgeRating.metron FK into AgeRatingMetron.
        "fts_age_rating_tagged": F("age_rating__name"),
        "fts_age_rating_metron": F("age_rating__metron__name"),
    }
)
# Alias → FK-traversal path. The alias becomes the FTS column name
# the consumer reads (``prepare.py:_COMIC_KEYS``); the path is what
# ``GROUP_CONCAT`` walks to extract the related ``name``. Decoupling
# the two fixes a long-standing bug: the previous code derived the
# alias from the path (``f"fts_{rel}"``), so paths with FK suffixes
# like ``credits__person`` produced aliases like
# ``fts_credits__person`` that the consumer's ``fts_credits`` lookup
# silently dropped — three FTS columns (credits, sources,
# story_arcs) ended up empty for sync-built entries.
_M2M_FTS_REL_MAP = MappingProxyType(
    {
        "characters": "characters__name",
        "credits": "credits__person__name",
        "genres": "genres__name",
        "locations": "locations__name",
        "series_groups": "series_groups__name",
        "sources": "identifiers__source__name",
        "stories": "stories__name",
        "story_arcs": "story_arc_numbers__story_arc__name",
        "tags": "tags__name",
        "teams": "teams__name",
    }
)


class SearchIndexerSync(SearchIndexerRemove):
    """Search Index update methods."""

    def _init_statuses(self, rebuild) -> None:
        """Initialize all statuses order before starting."""
        statii: list[Status] = []
        if rebuild:
            statii.append(
                SearchIndexClearStatus(),
            )
        else:
            statii.extend(
                [
                    SearchIndexCleanStatus(),
                    SearchIndexSyncUpdateStatus(),
                ]
            )
        statii.append(SearchIndexSyncCreateStatus())
        self.status_controller.start_many(statii)

    def _update_search_index_clean(self, rebuild) -> None:
        """Clear or clean the search index."""
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()
        else:
            self.remove_stale_records(log_success=False)

    @staticmethod
    def _build_fk_fts_rows(pks: list[int]) -> list[dict]:
        """
        One query: comic attrs + simple FK-resolved name columns.

        Returns a list of dicts keyed by ``id`` plus the FTS columns
        the consumer reads directly off Comic / FK ``__name``
        traversals (no M2M, no GROUP BY). Order-by-pk so the caller
        sees the same iteration order the megaquery used to produce.
        """
        return list(
            Comic.objects.filter(pk__in=pks)
            .order_by("pk")
            .annotate(**_SIMPLE_FTS_ANNOTATIONS)
            .values(
                "id",
                "name",
                "collection_title",
                "review",
                "summary",
                *_SIMPLE_FTS_ANNOTATIONS.keys(),
            )
        )

    @staticmethod
    def _build_m2m_fts_dict(pks: list[int], target_path: str) -> dict[int, str]:
        """
        One query per M2M: GROUP_CONCAT(<rel>__name) keyed by comic pk.

        Replaces the megaquery's per-M2M ``GROUP_CONCAT`` aggregations
        — each was a LEFT JOIN to the related table contributing to a
        cartesian product before GROUP BY collapse. Per-relation queries
        each walk one M2M's index independently and produce per-pk
        strings; no cartesian product, much smaller intermediate temp
        tables on richly-tagged libraries.
        """
        rows = (
            Comic.objects.filter(pk__in=pks)
            .annotate(
                fts_value=GroupConcat(target_path, distinct=True, order_by=target_path)
            )
            .values_list("pk", "fts_value")
        )
        # GROUP_CONCAT over a LEFT JOIN with no related rows returns
        # NULL → store empty string so the consumer's truthy filter
        # treats absence and emptiness identically.
        return {pk: (value or "") for pk, value in rows}

    @staticmethod
    def _build_universes_fts_dict(pks: list[int]) -> dict[int, str]:
        """
        Universes special case: Concat of designation + name aggregates.

        Universes carry both a ``designation`` and a ``name`` worth
        making searchable; the previous shape combined them via
        ``Concat(GroupConcat(designation), Value(","), GroupConcat(name))``.
        Single LEFT JOIN to the universes table, single GROUP BY on
        comic_id; same SQL as the megaquery would have produced for
        this column, just isolated from the other M2Ms.
        """
        rows = (
            Comic.objects.filter(pk__in=pks)
            .annotate(
                fts_universes=Concat(
                    GroupConcat(
                        "universes__designation",
                        distinct=True,
                        order_by="universes__designation",
                    ),
                    Value(","),
                    GroupConcat(
                        "universes__name",
                        distinct=True,
                        order_by="universes__name",
                    ),
                )
            )
            .values_list("pk", "fts_universes")
        )
        return {pk: (value or "") for pk, value in rows}

    def _update_search_index_operate_get_status(
        self, total_comics: int, chunk_human_size: str, *, create: bool
    ) -> SearchIndexSyncCreateStatus | SearchIndexSyncUpdateStatus:
        status_class = (
            SearchIndexSyncCreateStatus if create else SearchIndexSyncUpdateStatus
        )
        subtitle = f"Chunks of {chunk_human_size}" if total_comics else ""
        return status_class(total=total_comics, subtitle=subtitle)

    def _update_search_index_create_or_update(
        self,
        obj_list: list[ComicFTS],
        status,
        *,
        create: bool,
    ) -> None:
        if self.abort_event.is_set():
            return
        verb = "create" if create else "update"
        verbing = (verb[:-1] + "ing").capitalize()
        num_comic_fts = len(obj_list)

        batch_position = f"({status.complete}/{status.total})"
        self.log.debug(f"{verbing} {num_comic_fts} {batch_position} search entries...")
        if create:
            ComicFTS.objects.bulk_create(obj_list)
        else:
            ComicFTS.objects.bulk_update(obj_list, COMICFTS_UPDATE_FIELDS)

        status.increment_complete(num_comic_fts)
        self.status_controller.update(status, notify=True)

    def _update_search_index_operate(
        self, comics_filtered_qs: QuerySet, *, create: bool
    ):
        # Smaller systems may run out of virtual memory unless this is auto governed.
        mem_limit_gb = get_mem_limit("g")
        search_index_batch_size = floor(
            (mem_limit_gb / IMPORTER_SEARCH_SYNC_BATCH_MEMORY_RATIO) * 1000
        )
        chunk_human_size = intcomma(search_index_batch_size)

        # Hoist the FTS-empty check out of the loop. After the first
        # batch lands on an initially-empty index, ComicFTS has rows
        # for the rest of the run; checking ``ComicFTS.objects.exists()``
        # per iteration just spends a SELECT to learn what we already
        # know. Decide once up-front and stash on the base queryset.
        if create and not ComicFTS.objects.exists():
            base_qs: QuerySet = Comic.objects.all()
        else:
            base_qs = comics_filtered_qs

        verb = "create" if create else "update"
        self.log.debug(f"Counting total search index entries to {verb}...")
        total_comics = base_qs.count()
        status = self._update_search_index_operate_get_status(
            total_comics, chunk_human_size, create=create
        )

        try:
            if not total_comics:
                self.log.debug(f"No search entries to {verb}.")
                return total_comics

            self.status_controller.start(status, notify=True)
            start = 0
            while start < total_comics:
                obj_list = []
                if self.abort_event.is_set():
                    break
                # Not using standard iterator chunking to control memory and really
                # do this in batches.
                self.log.debug(
                    f"Preparing up to {chunk_human_size} comics for search indexing..."
                )
                # Snapshot the batch's pk list once; every per-relation
                # query below filters against the same set so they
                # stitch back together cleanly in Python.
                batch_pks = list(
                    base_qs.order_by("pk").values_list("pk", flat=True)[
                        :search_index_batch_size
                    ]
                )
                if not batch_pks:
                    break

                # Per-M2M batched queries. Replaces the previous
                # megaquery (10 GROUP_CONCAT aggregations + 20+
                # LEFT JOINs + GROUP BY in a single SELECT) with one
                # SELECT per relation — each walks one M2M's index
                # independently, no cartesian product across the
                # 10 M2Ms.
                fk_rows = self._build_fk_fts_rows(batch_pks)
                m2m_dicts = {
                    f"fts_{alias}": self._build_m2m_fts_dict(batch_pks, target)
                    for alias, target in _M2M_FTS_REL_MAP.items()
                }
                universes_dict = self._build_universes_fts_dict(batch_pks)

                for comic in fk_rows:
                    pk = comic["id"]
                    for fts_alias, m2m_dict in m2m_dicts.items():
                        comic[fts_alias] = m2m_dict.get(pk, "")
                    comic["fts_universes"] = universes_dict.get(pk, "")
                    SearchEntryPrepare.prepare_sync_fts_entry(
                        comic, obj_list, create=create
                    )

                if not obj_list:
                    break
                self._update_search_index_create_or_update(
                    obj_list,
                    status,
                    create=create,
                )
                start += search_index_batch_size

        finally:
            self.status_controller.finish(status)
        return total_comics

    def _update_search_index_update(self):
        """Update out of date search entries."""
        out_of_date_comics = Comic.objects.filter(_ALL_FTS_COMIC_IDS_QUERY)
        self.log.debug("Looking for search index watermark...")
        fts_watermark = ComicFTS.objects.aggregate(max=Max("updated_at"))["max"]
        if fts_watermark:
            since = fts_watermark
            out_of_date_comics = out_of_date_comics.filter(updated_at__gt=fts_watermark)
        else:
            since = "the fracturing of the multiverse"
            fts_watermark = fts_watermark or _MIN_UTC_DATE
        self.log.info(f"Looking for search entries to update since {since}...")
        count = out_of_date_comics.count()
        self.log.debug(f"Found {count} comics with out of date search entries.")

        return self._update_search_index_operate(out_of_date_comics, create=False)

    def _update_search_index_create(self):
        """Create missing search entries."""
        self.log.info("Looking for missing search entries to create...")
        missing_comics = Comic.objects.all()
        count = None if ComicFTS.objects.exists() else missing_comics.count()
        missing_comics = missing_comics.exclude(_ALL_FTS_COMIC_IDS_QUERY)
        if count is None:
            count = missing_comics.count()

        self.log.debug(f"Found {count} comics missing from the search index.")
        return self._update_search_index_operate(missing_comics, create=True)

    def _update_search_index(self, *, rebuild: bool) -> None:
        """Update or Rebuild the search index."""
        self.log.debug("In update search index before init statii.")
        # ``monotonic()`` over ``time()`` for the elapsed reporting
        # below — wall-clock jumps (NTP / DST / manual adjustment)
        # would skew ``time() - start_time``. Mirrors the same fix
        # applied to other librarian threads in PR #623 / #624.
        start_time = monotonic()
        self._init_statuses(rebuild)

        if self.abort_event.is_set():
            return
        cleaned_count = self._update_search_index_clean(rebuild)
        if self.abort_event.is_set():
            return
        updated_count = self._update_search_index_update()
        if self.abort_event.is_set():
            return
        created_count = self._update_search_index_create()

        elapsed_time = monotonic() - start_time
        elapsed = naturaldelta(elapsed_time)
        if rebuild:
            cleaned = "cleared entire search index"
        elif cleaned_count:
            cleaned = f"cleaned {cleaned_count} stale entries"
        else:
            cleaned = ""
        updated = f"{updated_count} entries updated by sync" if updated_count else ""
        created = f"{created_count} entries created by sync" if created_count else ""
        summary_parts = filter(None, (cleaned, updated, created))
        summary = ", ".join(summary_parts)
        if not summary:
            summary = "found to be already synced"
        self.log.success(f"Search index {summary} in {elapsed}.")

    def update_search_index(self, *, rebuild: bool) -> None:
        """Update or Rebuild the search index."""
        self.abort_event.clear()
        try:
            self._update_search_index(rebuild=rebuild)
        except Exception:
            self.log.exception("Update search index")
        finally:
            if self.abort_event.is_set():
                self.log.info("Search Index update aborted early.")
            self.abort_event.clear()
            self.status_controller.finish_many(SEARCH_INDEX_STATII)
