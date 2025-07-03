"""Search Index update."""

from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from comicbox.identifiers import ID_SOURCE_NAME_MAP
from django.db.models.aggregates import Max
from django.db.models.expressions import F, Value
from django.db.models.functions import Concat
from django.db.models.functions.datetime import Now
from django.db.models.query import QuerySet
from humanize import intcomma, naturaldelta

from codex.librarian.scribe.search.remove import SearchIndexerRemove
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status
from codex.models import Comic
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat
from codex.serializers.fields.browser import CountryField, LanguageField, PyCountryField
from codex.settings import SEARCH_INDEX_BATCH_SIZE

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
_CHUNK_HUMAN_SIZE = intcomma(SEARCH_INDEX_BATCH_SIZE)


class SearchIndexerSync(SearchIndexerRemove):
    """Search Index update methods."""

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        if rebuild:
            statii = [
                Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR),
            ]
        else:
            statii = [
                Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAN),
                Status(SearchIndexStatusTypes.SEARCH_INDEX_SYNC_UPDATE),
            ]
        statii.append(Status(SearchIndexStatusTypes.SEARCH_INDEX_SYNC_CREATE))
        self.status_controller.start_many(statii)

    def _update_search_index_clean(self, rebuild):
        """Clear or clean the search index."""
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()
        else:
            self.remove_stale_records()

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

    def _update_search_index_create_or_update(
        self,
        obj_list: list[ComicFTS],
        status,
        batch_status,
        *,
        create: bool,
    ):
        if self.abort_event.is_set():
            return
        verb = "create" if create else "update"
        verbed = verb.capitalize() + "d"
        verbing = (verb[:-1] + "ing").capitalize()
        num_comic_fts = len(obj_list)

        batch_position = f"({status.complete}/{status.total})"
        self.log.debug(f"{verbing} {num_comic_fts} {batch_position} search entries...")
        if create:
            ComicFTS.objects.bulk_create(obj_list)
        else:
            ComicFTS.objects.bulk_update(obj_list, _COMICFTS_UPDATE_FIELDS)
        self.log.info(
            f"{verbed} {num_comic_fts} {batch_position} search entries in {batch_status.elapsed()}, {batch_status.per_second('entries', num_comic_fts)}."
        )
        obj_list.clear()
        batch_status.reset()

    def _create_comicfts_entry(
        self,
        comic,
        obj_list: list[ComicFTS],
        status: Status,
        batch_status: Status,
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
        status.increment_complete()
        batch_status.increment_complete()
        self.status_controller.update(status)

    def _update_search_index_finish(self, status, *, create: bool):
        verb = "create" if create else "update"
        verbed = verb.capitalize() + "d"
        suffix = f"search entries in {status.elapsed()}"

        if status.complete:
            eps = status.per_second("entries")
            self.log.info(f"{verbed} {status.complete} {suffix}, {eps}.")
        else:
            self.log.debug(f"{verbed} no {suffix}.")
        self.status_controller.finish(status)

    def _update_search_index_operate_get_status(
        self, total_comics: int, *, create: bool
    ):
        status_type = (
            SearchIndexStatusTypes.SEARCH_INDEX_SYNC_CREATE
            if create
            else SearchIndexStatusTypes.SEARCH_INDEX_SYNC_UPDATE
        )
        subtitle = f"Chunks of {_CHUNK_HUMAN_SIZE}" if total_comics else ""
        return Status(status_type, total=total_comics, subtitle=subtitle)

    def _update_search_index_operate(
        self, comics_filtered_qs: QuerySet, *, create: bool
    ):
        total_comics = comics_filtered_qs.count()

        verb = "create" if create else "update"
        status = self._update_search_index_operate_get_status(
            total_comics, create=create
        )

        try:
            if total_comics:
                reason = (
                    f"Batching this search engine {verb} operation in to chunks of {_CHUNK_HUMAN_SIZE}."
                    f" Search engine {verb}s run much faster as one large batch but then there's no progress updates."
                    " You may adjust the batch size with the environment variable CODEX_SEARCH_INDEX_BATCH_SIZE."
                )
                self.log.debug(reason)
            else:
                self.log.info(f"No search entries to {verb}.")
                return total_comics

            self.status_controller.start(status)
            comics = self._select_related_fts_query(comics_filtered_qs)
            comics = self._prefetch_related_fts_query(comics)
            comics = self._annotate_fts_query(comics)
            comics = comics.order_by("pk")

            obj_list = []
            batch_status = Status(SearchIndexStatusTypes.SEARCH_INDEX_SYNC_UPDATE, 0)
            batch_status.start()
            prep_num = min(SEARCH_INDEX_BATCH_SIZE, total_comics)
            self.log.debug(f"Preparing {prep_num} comics for search indexing...")
            for comic in comics.iterator(chunk_size=SEARCH_INDEX_BATCH_SIZE):
                if self.abort_event.is_set():
                    break
                self._create_comicfts_entry(
                    comic, obj_list, status, batch_status, create=create
                )
                if len(obj_list) >= SEARCH_INDEX_BATCH_SIZE:
                    self._update_search_index_create_or_update(
                        obj_list,
                        status,
                        batch_status,
                        create=create,
                    )
                    complete = status.complete or 0
                    if prep_num := min(
                        SEARCH_INDEX_BATCH_SIZE, total_comics - complete
                    ):
                        self.log.debug(
                            f"Preparing {prep_num} comics for search indexing..."
                        )

            self._update_search_index_create_or_update(
                obj_list,
                status,
                batch_status,
                create=create,
            )

        finally:
            self._update_search_index_finish(status, create=create)
        return total_comics

    def _update_search_index_update(self):
        """Update out of date search entries."""
        fts_watermark = ComicFTS.objects.aggregate(max=Max("updated_at"))["max"]
        since = fts_watermark or "the fracturing of the multiverse"
        self.log.info(f"Looking for search entries to update since {since}...")
        fts_watermark = fts_watermark or _MIN_UTC_DATE
        out_of_date_comics = (
            Comic.objects.select_related("comicfts")
            .exclude(comicfts__isnull=True)
            .filter(updated_at__gt=fts_watermark)
        )
        return self._update_search_index_operate(out_of_date_comics, create=False)

    def _update_search_index_create(self):
        """Create missing search entries."""
        self.log.info("Looking for missing search entries to create...")
        missing_comics = Comic.objects.filter(comicfts__isnull=True)
        return self._update_search_index_operate(missing_comics, create=True)

    def _update_search_index(self, *, rebuild: bool):
        """Update or Rebuild the search index."""
        start_time = time()
        self._init_statuses(rebuild)

        if self.abort_event.is_set():
            return
        self._update_search_index_clean(rebuild)
        if self.abort_event.is_set():
            return
        updated_count = self._update_search_index_update()
        if self.abort_event.is_set():
            return
        created_count = self._update_search_index_create()

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        cleaned = "cleared" if rebuild else "cleaned"
        updated = f"{updated_count} entries updated" if updated_count else ""
        created = f"{created_count} entries created" if created_count else ""
        summary_parts = filter(None, (cleaned, updated, created))
        summary = ", ".join(summary_parts)
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
            self.status_controller.finish_many(SearchIndexStatusTypes.values)
