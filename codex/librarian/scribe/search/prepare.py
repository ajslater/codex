"""Prepare ComicFTS objects."""

from contextlib import suppress
from types import MappingProxyType

from comicbox.enums.comicbox import IdSources
from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from django.db.models.functions.datetime import Now

from codex.librarian.status import Status
from codex.models.comic import ComicFTS
from codex.serializers.fields.browser import CountryField, LanguageField

_PYCOUNTRY_FIELDS = MappingProxyType(
    {"country": CountryField(), "language": LanguageField()}
)
_COMIC_KEYS = (
    "collection_title",
    "country",
    "language",
    "name",
    "review",
    "summary",
    "fts_publisher",
    "fts_imprint",
    "fts_series",
    "fts_age_rating",
    "fts_original_format",
    "fts_scan_info",
    "fts_tagger",
    "fts_characters",
    "fts_credits",
    "fts_country",
    "fts_genres",
    "fts_sources",
    "fts_language",
    "fts_locations",
    "fts_series_groups",
    "fts_stories",
    "fts_story_arcs",
    "fts_tags",
    "fts_teams",
    "fts_universes",
)


class SearchEntryPrepare:
    """Prepare ComicFTS objects."""

    @staticmethod
    def _get_entry_str_value(entry: dict, key: str) -> str:
        value = entry.get(key)
        if not value:
            return ""
        if isinstance(value, tuple):
            value = value[0]
            if not value:
                return ""
        return value

    @staticmethod
    def _get_sources_fts_field(entry: dict) -> str:
        sources = entry.get("sources", ())
        if not sources:
            return ""
        if isinstance(sources, str):
            sources = (sources,)
        names = set()
        for source_str in sources:
            if not source_str:
                continue
            names.add(source_str)
            with suppress(ValueError):
                id_source = IdSources(source_str)
                if long_name := ID_SOURCE_NAME_MAP.get(id_source):
                    names.add(long_name)
        return ",".join(sorted(names))

    @classmethod
    def _get_pycountry_fts_field(cls, entry, field_name) -> str:
        iso_code = cls._get_entry_str_value(entry, field_name)
        if not iso_code:
            return ""
        field = _PYCOUNTRY_FIELDS[field_name]
        return ",".join((iso_code, field.to_representation(iso_code)))

    @classmethod
    def _create_comicfts_entry_attributes(cls, entry, *, create: bool):
        now = Now()
        entry["updated_at"] = now
        if create:
            entry["created_at"] = now

    @classmethod
    def _create_comicfts_entry_fks(cls, entry):
        entry["country"] = cls._get_pycountry_fts_field(entry, "country")
        entry["language"] = cls._get_pycountry_fts_field(entry, "language")

    @classmethod
    def _create_comicfts_entry_m2ms(cls, entry, existing_values: dict | None):
        if sources := cls._get_sources_fts_field(entry):
            entry["sources"] = sources
        if existing_values:
            for field_name in tuple(existing_values.keys()):
                if values := existing_values.get(field_name):
                    entry[field_name] = entry.get(field_name, ()) + values

    @classmethod
    def prepare_import_fts_entry(
        cls,
        comic_id: int,
        entry: dict,
        existing_m2m_values: dict | None,
        comicfts: ComicFTS | None,
        obj_list: list[ComicFTS],
        status: Status,
        *,
        create: bool,
    ):
        """Prepare ComicFTS object from import data."""
        cls._create_comicfts_entry_m2ms(entry, existing_m2m_values)
        cls._create_comicfts_entry_fks(entry)
        for field_name in entry:
            value = entry[field_name]
            if isinstance(value, tuple):
                entry[field_name] = ",".join(sorted(value))

        cls._create_comicfts_entry_attributes(entry, create=create)

        if comicfts:
            for field_name, value in entry.items():
                setattr(comicfts, field_name, value)
        else:
            entry["comic_id"] = comic_id
            comicfts = ComicFTS(**entry)

        obj_list.append(comicfts)
        status.increment_complete()

    @classmethod
    def prepare_sync_fts_entry(
        cls,
        comic: dict,
        obj_list: list[ComicFTS],
        *,
        create: bool,
    ):
        """Prepare ComicFTS object from sync query data."""
        entry = {
            key.removeprefix("fts_"): comic.get(key, "")
            for key in _COMIC_KEYS
            if comic.get(key)
        }
        if sources := cls._get_sources_fts_field(entry):
            entry["sources"] = sources
        cls._create_comicfts_entry_fks(entry)
        entry["universes"] = entry["universes"].strip(",")
        cls._create_comicfts_entry_attributes(entry, create=create)
        entry["comic_id"] = comic["id"]

        comicfts: ComicFTS = ComicFTS(**entry)
        obj_list.append(comicfts)
