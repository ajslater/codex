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
    "path",
    "reading_direction",
    "review",
    "scan_info",
    "summary",
    "tagger",
    # ManyToMany
    "characters",
    "contributors",
    "genres",
    "identifiers",
    "identifier_types",
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
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    )

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE)]
        if not rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
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
            fts_country=GroupConcat("country__name", distinct=True),
            fts_language=GroupConcat("language__name", distinct=True),
            fts_scan_info=F("scan_info__name"),
            fts_tagger=F("tagger__name"),
            fts_characters=GroupConcat("characters__name", distinct=True),
            fts_contributors=GroupConcat("contributors__person__name", distinct=True),
            fts_genres=GroupConcat("genres__name", distinct=True),
            fts_identifiers=GroupConcat("identifiers__nss", distinct=True),
            fts_identifier_types=GroupConcat(
                "identifiers__identifier_type__name", distinct=True
            ),
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
    def _get_pycountry_fts_field(field_instance: PyCountryField, iso_code: str | None):
        if iso_code:
            return iso_code + " " + field_instance.to_representation(iso_code)
        return ""

    def _update_search_index_create(self):
        """Create missing search entries."""
        missing_comics = Comic.objects.filter(comicfts__isnull=True)
        missing_comics = self._annotate_fts_query(missing_comics)
        create_comicfts = []
        country_field = CountryField()
        language_field = LanguageField()
        for comic in missing_comics:
            country = self._get_pycountry_fts_field(country_field, comic.fts_country)
            language = self._get_pycountry_fts_field(language_field, comic.fts_language)

            now = Now()
            comicfts = ComicFTS(
                comic_id=comic.pk,
                updated_at=now,
                created_at=now,
                publisher=comic.fts_publisher,
                imprint=comic.fts_imprint,
                series=comic.fts_series,
                volume=comic.fts_volume,
                issue=comic.issue,
                name=comic.name,
                age_rating=comic.age_rating,
                file_type=comic.file_type,
                country=country,
                language=language,
                notes=comic.notes,
                original_format=comic.original_format,
                path=comic.search_path,
                reading_direction=comic.reading_direction,
                review=comic.review,
                scan_info=comic.fts_scan_info,
                summary=comic.summary,
                tagger=comic.fts_tagger,
                # ManyToMany
                characters=comic.fts_characters,
                contributors=comic.fts_contributors,
                genres=comic.fts_genres,
                identifiers=comic.fts_identifiers,
                identifier_types=comic.fts_identifier_types,
                locations=comic.fts_locations,
                series_groups=comic.fts_series_groups,
                stories=comic.fts_stories,
                story_arcs=comic.fts_story_arcs,
                tags=comic.fts_tags,
                teams=comic.fts_teams,
            )
            create_comicfts.append(comicfts)

        ComicFTS.objects.bulk_create(create_comicfts)
        count = len(create_comicfts)
        if count:
            self.log.info(f"Created {count} search entries.")
        else:
            self.log.debug("Created no search entries.")

    def _update_search_index_update(self):
        """Update out of date search entries."""
        out_of_date_comics = Comic.objects.alias(
            fts_watermark=Max("comicfts__updated_at", default=_MIN_UTC_DATE)
        ).filter(updated_at__gt=F("fts_watermark"))
        out_of_date_comics = self._annotate_fts_query(out_of_date_comics)

        country_field = CountryField()
        language_field = LanguageField()
        update_comicfts = []
        for comic in out_of_date_comics:
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
                path=comic.search_path,
                reading_direction=comic.reading_direction,
                review=comic.review,
                scan_info=comic.fts_scan_info,
                summary=comic.summary,
                tagger=comic.fts_tagger,
                # ManyToMany
                characters=comic.fts_characters,
                contributors=comic.fts_contributors,
                genres=comic.fts_genres,
                identifiers=comic.fts_identifiers,
                identifier_types=comic.fts_identifier_types,
                locations=comic.fts_locations,
                series_groups=comic.fts_series_groups,
                stories=comic.fts_stories,
                story_arcs=comic.fts_story_arcs,
                tags=comic.fts_tags,
                teams=comic.fts_teams,
            )
            update_comicfts.append(comicfts)

        ComicFTS.objects.bulk_update(update_comicfts, _COMICFTS_UPDATE_FIELDS)
        count = len(update_comicfts)
        if count:
            self.log.info(f"Updated {count} search entries.")
        else:
            self.log.debug("Updated no search entries.")

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

        self._update_search_index_clean(rebuild)
        self._update_search_index_create()
        self._update_search_index_update()

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
