"""Search Index update."""

from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from django.db.models.aggregates import Max
from django.db.models.expressions import F, Value
from django.db.models.functions import Concat
from django.db.models.functions.datetime import Now
from django.db.models.query import QuerySet
from humanize import intword, naturaldelta

from codex.librarian.scribe.search.remove import SearchIndexerRemove
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status
from codex.models import Comic
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat
from codex.serializers.fields.browser import CountryField, LanguageField, PyCountryField
from codex.settings import SEARCH_INDEX_BATCH_SIZE

_COMICFTS_UPDATE_FIELDS = (
    # ForeignKeys
    "publisher",
    "imprint",
    "series",
    # Attributes
    "age_rating",
    "country",
    "collection_title",
    "file_type",
    "issue",
    "language",
    "name",
    "notes",
    "original_format",
    "reading_direction",
    "review",
    "scan_info",
    "summary",
    "tagger",
    # ManyToMany
    "characters",
    "credits",
    "genres",
    "locations",
    "series_groups",
    "stories",
    "story_arcs",
    "tags",
    "teams",
    "universes",
    # Base
    "updated_at",
)
_MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
_CHUNK_HUMAN_SIZE = intword(SEARCH_INDEX_BATCH_SIZE)


class SearchIndexerUpdate(SearchIndexerRemove):
    """Search Index update methods."""

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        else:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
        statii += [
            Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE),
            Status(SearchIndexStatusTypes.SEARCH_INDEX_CREATE),
        ]
        self.status_controller.start_many(statii)

    def _update_search_index_clean(self, rebuild):
        """Clear or clean the search index."""
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()
        else:
            self.remove_stale_records()

    @classmethod
    def _annotate_fts_query(cls, qs):
        return qs.annotate(
            fts_publisher=F("publisher__name"),
            fts_imprint=F("imprint__name"),
            fts_series=F("series__name"),
            fts_country=F("country__name"),
            fts_language=F("language__name"),
            fts_scan_info=F("scan_info__name"),
            fts_tagger=F("tagger__name"),
            fts_characters=GroupConcat("characters__name", distinct=True),
            fts_credits=GroupConcat("credits__person__name", distinct=True),
            fts_identifiers=GroupConcat("identifiers__key", distinct=True),
            fts_sources=GroupConcat("identifiers__source__name", distinct=True),
            fts_genres=GroupConcat("genres__name", distinct=True),
            fts_locations=GroupConcat("locations__name", distinct=True),
            fts_series_groups=GroupConcat("series_groups__name", distinct=True),
            fts_stories=GroupConcat("stories__name", distinct=True),
            fts_story_arcs=GroupConcat(
                "story_arc_numbers__story_arc__name", distinct=True
            ),
            fts_tags=GroupConcat("tags__name", distinct=True),
            fts_teams=GroupConcat("teams__name", distinct=True),
            fts_universes=Concat(
                GroupConcat("universes__name", distinct=True),
                Value(" "),
                GroupConcat("universes__designation", distinct=True),
            ),
        )

    @staticmethod
    def _get_pycountry_fts_field(field: PyCountryField, iso_code):
        if not iso_code:
            return ""
        return ",".join((iso_code, field.to_representation(iso_code)))

    def _get_comicfts_list(self, comics, *, create: bool):
        """Create a ComicFTS object for bulk_create or bulk_update."""
        country_field: PyCountryField = CountryField()  # pyright: ignore[reportAssignmentType]
        language_field: PyCountryField = LanguageField()  # pyright: ignore[reportAssignmentType]
        obj_list = []
        comics = self._annotate_fts_query(comics)
        for comic in comics:
            if self.is_abort():
                return obj_list

            country = self._get_pycountry_fts_field(country_field, comic.fts_country)
            language = self._get_pycountry_fts_field(language_field, comic.fts_language)

            now = Now()
            comicfts = ComicFTS(
                comic_id=comic.pk,
                # Attributes
                collection_title=comic.collection_title,
                issue=comic.issue,
                name=comic.name,
                notes=comic.notes,
                review=comic.review,
                updated_at=now,
                # Group FKs
                publisher=comic.fts_publisher,
                imprint=comic.fts_imprint,
                series=comic.fts_series,
                # FKS
                age_rating=comic.age_rating,
                country=country,
                file_type=comic.file_type,
                language=language,
                original_format=comic.original_format,
                reading_direction=comic.reading_direction,
                scan_info=comic.fts_scan_info,
                summary=comic.summary,
                tagger=comic.fts_tagger,
                # ManyToMany
                characters=comic.fts_characters,
                credits=comic.fts_credits,
                genres=comic.fts_genres,
                identifiers=comic.fts_identifiers,
                sources=comic.fts_sources,
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

        return obj_list

    def _update_search_index_finish(
        self, count, verbed, prepare_status, operate_status, start_time
    ):
        self.status_controller.finish(prepare_status)
        total_time = time() - start_time
        human_time = naturaldelta(total_time)
        if total_time:
            eps = round(count / total_time)
            eps_suffix = f", {eps} per second."
        else:
            eps_suffix = "."
        suffix = f"search entries in {human_time}{eps_suffix}."
        if count:
            self.log.info(f"{verbed} {count} {suffix}")
        else:
            self.log.debug(f"{verbed} no {suffix}.")
        self.status_controller.finish(operate_status)

    def _update_search_index_operate_batch(  # noqa: PLR0913
        self,
        comics_qs: QuerySet,
        batch_from: int,
        count: int,
        verbing: str,
        verbed: str,
        prepare_status,
        operate_status,
        *,
        create: bool,
    ):
        if self.is_abort():
            return
        batch_start = time()
        batch_to = batch_from + SEARCH_INDEX_BATCH_SIZE
        batch_min_to = min(batch_to, count)
        batch_count = batch_min_to - batch_from
        batch_position = f"({batch_from}:{batch_min_to}/{count})"
        self.log.debug(
            f"Preparing {batch_count} {batch_position} comics for search indexing..."
        )
        comics_batch = comics_qs[batch_from:batch_to]
        if prepare_status.complete is None:
            prepare_status.complete = 0
            self.status_controller.update(prepare_status, notify=True)
        operate_comicfts = self._get_comicfts_list(comics_batch, create=create)
        operate_comicfts_count = len(operate_comicfts)
        prepare_status.add_complete(operate_comicfts_count)
        self.status_controller.update(prepare_status)
        if prepare_status.complete and prepare_status.complete >= prepare_status.total:
            self.status_controller.finish(prepare_status)
        if self.is_abort():
            return
        self.log.debug(
            f"{verbing} {operate_comicfts_count} {batch_position}) search entries..."
        )
        if operate_status.complete is None:
            operate_status.add_complete(0)
            self.status_controller.update(operate_status, notify=True)
        if create:
            ComicFTS.objects.bulk_create(operate_comicfts)
        else:
            ComicFTS.objects.bulk_update(operate_comicfts, _COMICFTS_UPDATE_FIELDS)
        operate_status.add_complete(operate_comicfts_count)
        self.status_controller.update(operate_status)
        batch_time = time() - batch_start
        human_time = naturaldelta(batch_time)
        eps = round(count / batch_time)
        self.log.debug(
            f"{verbed} {operate_comicfts_count} {batch_position} search entries in {human_time}, {eps} per second."
        )

    def _update_search_index_operate(self, comics_qs, *, create: bool):
        count = comics_qs.count()
        verb = "create" if create else "update"
        if not count:
            self.log.info(f"No search entries to {verb}.")

        if count > SEARCH_INDEX_BATCH_SIZE:
            reason = (
                f"Batching this search engine {verb} operation in to chunks of {_CHUNK_HUMAN_SIZE}."
                f" Search engine {verb}s run much faster as one large batch but then there's no progress updates."
                " You may adjust the batch size with the environment variable CODEX_SEARCH_INDEX_BATCH_SIZE."
            )
            self.log.debug(reason)
            subtitle = f"Chunks of {_CHUNK_HUMAN_SIZE}"
        else:
            subtitle = ""

        status_type = (
            SearchIndexStatusTypes.SEARCH_INDEX_CREATE
            if create
            else SearchIndexStatusTypes.SEARCH_INDEX_UPDATE
        )
        operate_status = Status(status_type, total=count, subtitle=subtitle)
        self.status_controller.start(operate_status)
        prepare_status = Status(
            SearchIndexStatusTypes.SEARCH_INDEX_PREPARE, total=count, subtitle=subtitle
        )
        self.status_controller.start(prepare_status)

        verbing = (verb[:-1] + "ing").capitalize()
        verbed = verb.capitalize() + "d"
        batch_from = 0
        start_time = time()
        try:
            while batch_from < count:
                self._update_search_index_operate_batch(
                    comics_qs,
                    batch_from,
                    count,
                    verbing,
                    verbed,
                    prepare_status,
                    operate_status,
                    create=create,
                )
                if self.is_abort():
                    break
                batch_from += SEARCH_INDEX_BATCH_SIZE
        finally:
            self._update_search_index_finish(
                count, verbed, operate_status, prepare_status, start_time
            )

    def _update_search_index_update(self, all_indexed_comic_ids):
        """Update out of date search entries."""
        fts_watermark = ComicFTS.objects.aggregate(max=Max("updated_at"))["max"]
        if not fts_watermark:
            fts_watermark = _MIN_UTC_DATE
            since = "the fracturing of the multiverse"
        else:
            since = fts_watermark
        self.log.info(f"Looking for search entries to update since {since}...")
        out_of_date_comics = Comic.objects.filter(
            pk__in=all_indexed_comic_ids, updated_at__gt=fts_watermark
        )
        self._update_search_index_operate(out_of_date_comics, create=False)

    def _update_search_index_create(self, all_indexed_comic_ids):
        """Create missing search entries."""
        self.log.info("Looking for missing search entries to create...")
        missing_comics = Comic.objects.all()
        if len(all_indexed_comic_ids):
            missing_comics = missing_comics.exclude(pk__in=all_indexed_comic_ids)
        self._update_search_index_operate(missing_comics, create=True)

    def _update_search_index(self, start_time, rebuild):
        """Update or Rebuild the search index."""
        self._init_statuses(rebuild)

        if self.is_abort():
            return
        self._update_search_index_clean(rebuild)
        if self.is_abort():
            return
        all_indexed_comic_ids = ComicFTS.objects.values_list("comic_id", flat=True)
        if self.is_abort():
            return
        self._update_search_index_update(all_indexed_comic_ids)
        if self.is_abort():
            return
        self._update_search_index_create(all_indexed_comic_ids)

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        self.log.success(f"Search index updated in {elapsed}.")
        self.abort_event.clear()

    def update_search_index(self, *, rebuild: bool):
        """Update or Rebuild the search index."""
        start_time = time()
        self.abort_event.clear()
        try:
            self._update_search_index(start_time, rebuild)
            if self.is_abort():
                self.log.debug("Search engine update aborted on signal.")
        except Exception:
            self.log.exception("Update search index")
        finally:
            self.abort_event.clear()
            self.status_controller.finish_many(SearchIndexStatusTypes.values)
