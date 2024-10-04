"""Search Index update."""

from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from django.db.models.aggregates import Max
from django.db.models.expressions import F
from django.db.models.functions.datetime import Now
from humanize import naturaldelta

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.models import Comic, Library
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat
from codex.serializers.fields import CountryField, LanguageField, PyCountryField
from codex.settings.settings import SEARCH_INDEX_BATCH_SIZE
from codex.status import Status

_COMICFTS_UPDATE_FIELDS = (
    # ForeignKeys
    "publisher",
    "imprint",
    "series",
    "volume",
    # Attributes
    "age_rating",
    "file_type",
    "country",
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
    "contributors",
    "genres",
    "locations",
    "series_groups",
    "stories",
    "story_arcs",
    "tags",
    "teams",
    # Base
    "updated_at",
)
_MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))


class FTSUpdateMixin(RemoveMixin):
    """Search Index update methods."""

    _STATUS_FINISH_TYPES = (
        SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
        SearchIndexStatusTypes.SEARCH_INDEX_CREATE,
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    )

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
            fts_volume=F("volume__name"),
            fts_country=F("country__name"),
            fts_language=F("language__name"),
            fts_scan_info=F("scan_info__name"),
            fts_tagger=F("tagger__name"),
            fts_characters=GroupConcat("characters__name", distinct=True),
            fts_contributors=GroupConcat("contributors__person__name", distinct=True),
            fts_genres=GroupConcat("genres__name", distinct=True),
            fts_locations=GroupConcat("locations__name", distinct=True),
            fts_series_groups=GroupConcat("series_groups__name", distinct=True),
            fts_stories=GroupConcat("stories__name", distinct=True),
            fts_story_arcs=GroupConcat(
                "story_arc_numbers__story_arc__name", distinct=True
            ),
            fts_tags=GroupConcat("tags__name", distinct=True),
            fts_teams=GroupConcat("teams__name", distinct=True),
        )

    @staticmethod
    def _get_pycountry_fts_field(field_instance: PyCountryField, iso_code):
        if not iso_code:
            return ""
        return ",".join((iso_code, field_instance.to_representation(iso_code)))

    def _get_comicts_fts_list(
        self, comics, country_field, language_field, obj_list, create
    ):
        """Prepare a batch of search entries."""
        for comic in comics:
            country = self._get_pycountry_fts_field(country_field, comic.fts_country)
            language = self._get_pycountry_fts_field(language_field, comic.fts_language)

            now = Now()
            comicfts = ComicFTS(
                comic_id=comic.pk,
                updated_at=now,
                publisher=comic.fts_publisher,
                imprint=comic.fts_imprint,
                series=comic.fts_series,
                volume=comic.fts_volume,
                issue=comic.issue,
                name=comic.name,
                age_rating=comic.age_rating,
                country=country,
                file_type=comic.file_type,
                language=language,
                notes=comic.notes,
                original_format=comic.original_format,
                reading_direction=comic.reading_direction,
                review=comic.review,
                scan_info=comic.fts_scan_info,
                summary=comic.summary,
                tagger=comic.fts_tagger,
                # ManyToMany
                characters=comic.fts_characters,
                contributors=comic.fts_contributors,
                genres=comic.fts_genres,
                locations=comic.fts_locations,
                series_groups=comic.fts_series_groups,
                stories=comic.fts_stories,
                story_arcs=comic.fts_story_arcs,
                tags=comic.fts_tags,
                teams=comic.fts_teams,
            )
            if create:
                comicfts.created_at = now
            obj_list.append(comicfts)

    def _get_comicfts_list(self, comics, create=False):
        """Create a ComicFTS object for bulk_create or bulk_update."""
        country_field = CountryField()
        language_field = LanguageField()
        obj_list = []
        comics = self._annotate_fts_query(comics)
        self._get_comicts_fts_list(
            comics, country_field, language_field, obj_list, create
        )
        return obj_list

    def _update_search_index_finish(self, count, verb, status):
        verb = verb.capitalize() + "d"
        if count:
            self.log.info(f"{verb} {count} search entries.")
        else:
            self.log.debug(f"{verb} no search entries.")
        self.status_controller.finish(status)

    def _update_search_index_operate(self, comics_qs, create=False):
        count = comics_qs.count()
        verb = "create" if create else "update"
        if not count:
            self.log.info(f"No search entries to {verb}.")

        if count > SEARCH_INDEX_BATCH_SIZE:
            self.log.debug(
                f"Batching this search engine {verb} operation in to chunks of {SEARCH_INDEX_BATCH_SIZE}."
                f" Search engine {verb}s run much faster as one large batch but then there's no progress updates."
                " You may adjust the batch size with the environment variable CODEX_SEARCH_INDEX_BATCH_SIZE."
            )

        status_type = (
            SearchIndexStatusTypes.SEARCH_INDEX_CREATE
            if create
            else SearchIndexStatusTypes.SEARCH_INDEX_UPDATE
        )
        complete = None if count <= SEARCH_INDEX_BATCH_SIZE else 0
        operate_status = Status(status_type, complete, count)
        self.status_controller.start(operate_status)

        batch_from = 0
        try:
            while batch_from < count:
                batch_start = time()
                batch_to = batch_from + SEARCH_INDEX_BATCH_SIZE
                comics_batch = comics_qs[batch_from:batch_to]

                if self.abort_event.is_set():
                    break
                operate_comicfts = self._get_comicfts_list(comics_batch, create)
                operate_comicfts_count = len(operate_comicfts)
                if self.abort_event.is_set():
                    break
                if create:
                    ComicFTS.objects.bulk_create(operate_comicfts)
                else:
                    ComicFTS.objects.bulk_update(
                        operate_comicfts, _COMICFTS_UPDATE_FIELDS
                    )
                operate_status.add_complete(operate_comicfts_count)
                self.status_controller.update(operate_status)
                batch_time = time() - batch_start
                eps = round(count / batch_time)
                self.log.debug(
                    f"{verb} {count}/{operate_comicfts_count} search entries in {batch_time}, {eps} per second."
                )
                batch_from = batch_to
        finally:
            self._update_search_index_finish(count, verb, operate_status)

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
        any_update_in_progress = Library.objects.filter(
            covers_only=False, update_in_progress=True
        ).exists()
        if any_update_in_progress:
            self.log.debug(
                "Database update in progress, not updating search index yet."
            )
            return

        self._init_statuses(rebuild)

        if self.abort_event.is_set():
            return
        self._update_search_index_clean(rebuild)
        if self.abort_event.is_set():
            return
        all_indexed_comic_ids = ComicFTS.objects.values_list("comic_id", flat=True)
        if self.abort_event.is_set():
            return
        self._update_search_index_update(all_indexed_comic_ids)
        if self.abort_event.is_set():
            return
        self._update_search_index_create(all_indexed_comic_ids)

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        self.log.info(f"Search index updated in {elapsed}.")

    def update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start_time = time()
        self.abort_event.clear()
        try:
            self._update_search_index(start_time, rebuild)
        except Exception:
            self.log.exception("Update search index")
        finally:
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES)
