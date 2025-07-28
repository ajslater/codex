"""Search Index update."""

from datetime import datetime
from math import floor
from time import time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from django.db.models.aggregates import Max
from django.db.models.expressions import F, Value
from django.db.models.functions import Concat
from django.db.models.functions.datetime import Now
from django.db.models.query import QuerySet
from humanize import intcomma, naturaldelta

from codex.librarian.memory import get_mem_limit
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
from codex.serializers.fields.browser import CountryField, LanguageField, PyCountryField
from codex.settings import SEARCH_SYNC_BATCH_MEMORY_RATIO

if TYPE_CHECKING:
    from codex.librarian.status import Status

_COMICFTS_ATTRIBUTES = (
    "collection_title",
    "file_type",
    "issue",
    "name",
    "notes",
    "reading_direction",
    "review",
    "summary",
    "updated_at",
)
_COMICFTS_FKS = (
    "publisher",
    "imprint",
    "series",
    "age_rating",
    "country",
    "language",
    "original_format",
    "scan_info",
    "tagger",
)
_COMICFTS_M2MS = (
    "characters",
    "credits",
    "genres",
    "identifiers",
    "locations",
    "series_groups",
    "sources",
    "stories",
    "story_arcs",
    "tags",
    "teams",
    "universes",
)
_COMICFTS_UPDATE_FIELDS = (
    *_COMICFTS_ATTRIBUTES,
    *_COMICFTS_FKS,
    *_COMICFTS_M2MS,
)
_MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))


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
            # Group Fks
            fts_publisher=F("publisher__name"),
            fts_imprint=F("imprint__name"),
            fts_series=F("series__name"),
            # Fks
            fts_age_rating=F("age_rating__name"),
            fts_country=F("country__name"),
            fts_original_format=F("original_format__name"),
            fts_language=F("language__name"),
            fts_scan_info=F("scan_info__name"),
            fts_tagger=F("tagger__name"),
            # M2ms
            fts_characters=GroupConcat("characters__name", distinct=True),
            fts_credits=GroupConcat("credits__person__name", distinct=True),
            fts_genres=GroupConcat("genres__name", distinct=True),
            fts_identifiers=GroupConcat("identifiers__key", distinct=True),
            fts_locations=GroupConcat("locations__name", distinct=True),
            fts_series_groups=GroupConcat("series_groups__name", distinct=True),
            fts_sources=GroupConcat("identifiers__source__name", distinct=True),
            fts_stories=GroupConcat("stories__name", distinct=True),
            fts_story_arcs=GroupConcat(
                "story_arc_numbers__story_arc__name", distinct=True
            ),
            fts_tags=GroupConcat("tags__name", distinct=True),
            fts_teams=GroupConcat("teams__name", distinct=True),
            fts_universes=Concat(
                GroupConcat("universes__name", distinct=True),
                Value(","),
                GroupConcat("universes__designation", distinct=True),
            ),
        )

    @staticmethod
    def _get_pycountry_fts_field(field: PyCountryField, iso_code) -> str:
        if not iso_code:
            return ""
        return ",".join((iso_code, field.to_representation(iso_code)))

    @staticmethod
    def _get_sources_fts_field(sources) -> str | None:
        names = []
        if not sources:
            return None
        for source in sources.split(","):
            names.append(source)
            if long_name := ID_SOURCE_NAME_MAP.get(source):
                names.append(long_name)
        return ",".join(names)

    def _update_search_index_operate_get_status(
        self, total_comics: int, chunk_human_size: str, *, create: bool
    ):
        status_class = (
            SearchIndexSyncCreateStatus if create else SearchIndexSyncUpdateStatus
        )
        subtitle = f"Chunks of {chunk_human_size}" if total_comics else ""
        return status_class(total=total_comics, subtitle=subtitle)

    def _create_comicfts_entry(
        self,
        comic,
        obj_list: list[ComicFTS],
        *,
        create: bool,
    ):
        country_field: PyCountryField = CountryField()  # pyright: ignore[reportAssignmentType]
        language_field: PyCountryField = LanguageField()  # pyright: ignore[reportAssignmentType]

        country = self._get_pycountry_fts_field(country_field, comic.fts_country)
        language = self._get_pycountry_fts_field(language_field, comic.fts_language)
        sources = self._get_sources_fts_field(comic.fts_sources)

        now = Now()
        comicfts = ComicFTS(
            comic_id=comic.pk,
            # Attributes
            collection_title=comic.collection_title,
            file_type=comic.file_type,
            issue=comic.issue(),
            name=comic.name,
            notes=comic.notes,
            reading_direction=comic.reading_direction,
            review=comic.review,
            summary=comic.summary,
            updated_at=now,
            # Group FKs
            publisher=comic.fts_publisher,
            imprint=comic.fts_imprint,
            series=comic.fts_series,
            # FKS
            age_rating=comic.fts_age_rating,
            country=country,
            language=language,
            original_format=comic.fts_original_format,
            scan_info=comic.fts_scan_info,
            tagger=comic.fts_tagger,
            # ManyToMany
            characters=comic.fts_characters,
            credits=comic.fts_credits,
            genres=comic.fts_genres,
            identifiers=comic.fts_identifiers,
            sources=sources,  # comic.fts_sources,
            locations=comic.fts_locations,
            series_groups=comic.fts_series_groups,
            stories=comic.fts_stories,
            story_arcs=comic.fts_story_arcs,
            tags=comic.fts_tags,
            teams=comic.fts_teams,
            universes=comic.fts_universes,
        )
        if create:
            comicfts.created_at = now

        obj_list.append(comicfts)

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
            ComicFTS.objects.bulk_update(obj_list, _COMICFTS_UPDATE_FIELDS)

        status.increment_complete(num_comic_fts)
        self.status_controller.update(status, notify=True)

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
        total_comics = comics_filtered_qs.count()
        status = self._update_search_index_operate_get_status(
            total_comics, chunk_human_size, create=create
        )

        try:
            if not total_comics:
                self.log.debug(f"No search entries to {verb}.")
                return total_comics

            self.status_controller.start(status, notify=True)
            while True:
                obj_list = []
                if self.abort_event.is_set():
                    break
                # Not using standard iterator chunking to control memory and really
                # do this in batches.
                self.log.debug(
                    f"Preparing up to {search_index_batch_size} comics for search indexing..."
                )
                comics = comics_filtered_qs
                comics = self._select_related_fts_query(comics)
                comics = self._prefetch_related_fts_query(comics)
                comics = comics.order_by("pk")
                comics = comics[:search_index_batch_size]
                comics = self._annotate_fts_query(comics)
                for comic in comics:
                    self._create_comicfts_entry(comic, obj_list, create=create)

                if not obj_list:
                    break
                self._update_search_index_create_or_update(
                    obj_list,
                    status,
                    create=create,
                )

        finally:
            self.status_controller.finish(status)
        return total_comics

    def _update_search_index_update(self):
        """Update out of date search entries."""
        fts_watermark = ComicFTS.objects.aggregate(max=Max("updated_at"))["max"]
        since = fts_watermark or "the fracturing of the multiverse"
        self.log.info(f"Looking for search entries to update since {since}...")
        fts_watermark = fts_watermark or _MIN_UTC_DATE
        out_of_date_comics = Comic.objects.filter(
            comicfts__isnull=False, updated_at__gt=fts_watermark
        )
        return self._update_search_index_operate(out_of_date_comics, create=False)

    def _update_search_index_create(self):
        """Create missing search entries."""
        self.log.info("Looking for missing search entries to create...")
        missing_comics = Comic.objects.exclude(
            pk__in=ComicFTS.objects.values("comic_id")
        )
        return self._update_search_index_operate(missing_comics, create=True)

    def _update_search_index(self, *, rebuild: bool):
        """Update or Rebuild the search index."""
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
