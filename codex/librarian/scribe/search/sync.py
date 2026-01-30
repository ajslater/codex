"""Search Index update."""

from datetime import datetime
from math import floor
from time import time
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
from codex.settings import SEARCH_SYNC_BATCH_MEMORY_RATIO

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
    "age_rating",
    "country",
    "original_format",
    "language",
    "scan_info",
    "tagger",
)
_SIMPLE_FTS_ANNOTATIONS = MappingProxyType(
    {f"fts_{rel}": F(f"{rel}__name") for rel in _SIMPLE_FTS_FIELDS}
)
_M2M_FTS_RELS = (
    "characters",
    "credits__person",
    "genres",
    "locations",
    "series_groups",
    "identifiers__source",
    "stories",
    "story_arc_numbers__story_arc",
    "tags",
    "teams",
)
_M2M_FTS_ANNOTATIONS = MappingProxyType(
    {
        f"fts_{rel}": GroupConcat(
            f"{rel}__name",
            order_by=f"{rel}__name",
            distinct=True,
        )
        for rel in _M2M_FTS_RELS
    }
)


class SearchIndexerSync(SearchIndexerRemove):
    """Search Index update methods."""

    def _init_statuses(self, rebuild):
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

    def _update_search_index_clean(self, rebuild):
        """Clear or clean the search index."""
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()
        else:
            self.remove_stale_records(log_success=False)

    @staticmethod
    def _select_related_fts_query(qs):
        return qs.select_related(
            "publisher",
            "imprint",
            "series",
            "country",
            "language",
            "scan_info",
            "tagger",
        )

    @staticmethod
    def _prefetch_related_fts_query(qs):
        # Prefecthing deep relations breaks the 1000 sqlite query depth limit
        return qs.prefetch_related(
            "characters",
            "credits",
            # "credits__person",
            "identifiers",
            # "identifiers__source",
            "genres",
            "locations",
            "series_groups",
            "stories",
            "story_arc_numbers",
            # "story_arc_numbers__story_arc",
            "tags",
            "teams",
            "universes",
        )

    @staticmethod
    def _annotate_fts_query(qs):
        return qs.annotate(
            **_SIMPLE_FTS_ANNOTATIONS,
            **_M2M_FTS_ANNOTATIONS,
            fts_universes=Concat(
                GroupConcat(
                    "universes__designation",
                    distinct=True,
                    order_by="universes__designation",
                ),
                Value(","),
                GroupConcat(
                    "universes__name", distinct=True, order_by="universes__name"
                ),
            ),
        )

    def _update_search_index_operate_get_status(
        self, total_comics: int, chunk_human_size: str, *, create: bool
    ):
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
    ):
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

    @staticmethod
    def _get_operation_comics_query(qs, *, create: bool):
        if create and not ComicFTS.objects.exists():
            qs = Comic.objects.all()
        return qs

    def _update_search_index_operate(
        self, comics_filtered_qs: QuerySet, *, create: bool
    ):
        # Smaller systems may run out of virtual memory unless this is auto governed.
        mem_limit_gb = get_mem_limit("g")
        search_index_batch_size = floor(
            (mem_limit_gb / SEARCH_SYNC_BATCH_MEMORY_RATIO) * 1000
        )
        chunk_human_size = intcomma(search_index_batch_size)

        verb = "create" if create else "update"
        self.log.debug(f"Counting total search index entries to {verb}...")
        total_comics = self._get_operation_comics_query(
            comics_filtered_qs, create=create
        )
        total_comics = total_comics.count()
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
                # This query is supposed to get only comics that don't need creating but it doesn't
                # So the start total exit assists it with that.
                comics = self._get_operation_comics_query(
                    comics_filtered_qs, create=create
                )
                comics = self._prefetch_related_fts_query(comics)
                comics = comics.order_by("pk")
                comics = comics[:search_index_batch_size]
                comics = self._annotate_fts_query(comics)
                for comic in comics.values():
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

    def _update_search_index(self, *, rebuild: bool):
        """Update or Rebuild the search index."""
        self.log.debug("In update search index before init statii.")
        start_time = time()
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

        elapsed_time = time() - start_time
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

    def update_search_index(self, *, rebuild: bool):
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
