"""
Anonymous stats for library contents and reader usage.

Counts only, plus buckets keyed by closed vocabularies. Identifier source
names come from comic files, so they are mapped through comicbox's known
sources and anything unrecognized is collapsed to "other" before it can
leave the process.
"""

from types import MappingProxyType
from typing import Any, Final

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from django.db.models import Count

from codex.choices.api_key import ApiKeyScope
from codex.models.api_key import UserApiKey
from codex.models.bookmark import Bookmark
from codex.models.comic import Comic
from codex.models.identifier import Identifier, IdentifierType
from codex.models.library import Library
from codex.models.named import Credit, Reprint
from codex.models.paths import CustomCover, FailedImport
from codex.models.readinglist import (
    ITEM_COLLECTIONS,
    MISSING_Q,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.models.settings import SettingsBrowser

OTHER_IDENTIFIER_SOURCE: Final = "other"
# comicbox's closed source vocabulary. A source name read from a comic file
# that isn't in here is collapsed to "other" before it leaves the process.
IDENTIFIER_SOURCES: Final = frozenset(source.value for source in ID_SOURCE_NAME_MAP)

# Comic columns whose signal is "how many comics have this filled in".
_COMIC_POPULATED_FIELDS: Final = MappingProxyType(
    {
        "comic_community_rating_count": "community_rating",
        "comic_community_rating_vote_count": "community_rating_count",
        "comic_alternative_issue_number_count": "alternative_issue_number",
        "comic_metadata_imported_count": "metadata_imported_at",
    }
)
# Comic columns that are NOT NULL and mark "nothing here" with an empty value
# rather than with NULL, so the isnull idiom above would count every comic.
_COMIC_EMPTY_VALUES: Final = MappingProxyType(
    {
        "comic_manga_volume_count": ("manga_volume", ""),
        "comic_urls_count": ("urls", []),
    }
)
# The payload key each manga value is counted under. Written out rather than
# generated from MangaChoices so every key this module emits is fixed in codex
# source: a new comicbox manga value then fails the serializer-registration
# test instead of quietly inventing a payload key. The counts partition the
# library, so they sum to issue_count.
_MANGA_COUNT_KEYS: Final = MappingProxyType(
    {
        "yes": "comic_manga_yes_count",
        "no": "comic_manga_no_count",
        "unknown": "comic_manga_unknown_count",
    }
)
_MANGA_UNKNOWN_COUNT: Final = "comic_manga_unknown_count"
# The bucket a stored value outside its column's vocabulary is counted under.
_OTHER_BUCKET: Final = "other"
_ITEM_COLLECTION_KEYS: Final = frozenset(
    collection.value for collection in ITEM_COLLECTIONS
)
_SOURCE_KIND_KEYS: Final = frozenset(kind.value for kind in ReadingListSourceKind)


def get_library_stats() -> dict[str, int]:
    """Report how libraries and custom covers are configured."""
    covers = CustomCover.objects
    return {
        "library_read_only_count": Library.objects.filter(read_only=True).count(),
        "library_poll_count": Library.objects.filter(poll=True).count(),
        "library_events_count": Library.objects.filter(events=True).count(),
        "library_group_acl_count": Library.objects.filter(groups__isnull=False)
        .distinct()
        .count(),
        "custom_cover_count": covers.count(),
        # A null library means the cover was uploaded through the browser
        # rather than discovered in a covers directory.
        "custom_cover_uploaded_count": covers.filter(library__isnull=True).count(),
        "custom_cover_dir_count": covers.filter(library__isnull=False).count(),
        "failed_import_count": FailedImport.objects.count(),
    }


def get_comic_populated_stats() -> dict[str, int]:
    """Count comics carrying each of the newer comic columns."""
    return {
        name: Comic.objects.exclude(**{f"{field}__isnull": True}).count()
        for name, field in _COMIC_POPULATED_FIELDS.items()
    }


def get_comic_nonempty_stats() -> dict[str, int]:
    """
    Count comics carrying a value in a column whose empty state is not NULL.

    ``manga_volume`` defaults to "" and ``urls`` to [], both NOT NULL, so the
    isnull test :func:`get_comic_populated_stats` uses would report the whole
    library for either. Only the count of comics leaves here -- never a volume
    string, never a url, never how many urls a comic carries.
    """
    return {
        name: Comic.objects.exclude(**{field: empty}).count()
        for name, (field, empty) in _COMIC_EMPTY_VALUES.items()
    }


def get_metadata_flag_stats() -> dict[str, int]:
    """
    Count the tag rows carrying each comicbox 5 boolean.

    Rows, not comics: a credit is shared between the comics that name it. Both
    read zero on a library imported before comicbox 5 and stay there until the
    files are read again, which is a fact about the upgrade rather than about
    how anyone tags. Never broken down by role, person or series -- those are
    names, and the count is the whole signal.
    """
    return {
        "credit_primary_count": Credit.objects.filter(primary=True).count(),
        "reprint_alternative_name_count": Reprint.objects.filter(
            alternative_name=True
        ).count(),
    }


def get_manga_stats() -> dict[str, int]:
    """
    Count comics by whether they are manga.

    Three counts rather than a bucket, so the payload's keys stay fixed in
    codex source. A value outside the vocabulary is counted as unknown rather
    than dropped: the three counts partition the library either way, and a
    missing comic would be harder to notice than a mislabeled one. Every
    comic reads unknown until it is read again under comicbox 5.
    """
    stats = dict.fromkeys(_MANGA_COUNT_KEYS.values(), 0)
    rows = Comic.objects.values("manga").annotate(count=Count("pk")).order_by()
    for row in rows:
        # The column is nocase, so the stored spelling is not authoritative.
        key = _MANGA_COUNT_KEYS.get(str(row["manga"]).lower(), _MANGA_UNKNOWN_COUNT)
        stats[key] += row["count"]
    return stats


def _closed_bucket(queryset, field: str, vocabulary: frozenset[str]) -> dict[str, int]:
    """
    Count rows by one column, keyed only by that column's closed vocabulary.

    A stored value outside the vocabulary, whatever it holds, is counted
    under "other": every writer validates these columns today, but a stored
    value can be anything.
    """
    rows = queryset.values(field).annotate(count=Count("pk")).order_by()
    bucket: dict[str, int] = {}
    for row in rows:
        key = row[field]
        if key not in vocabulary:
            key = _OTHER_BUCKET
        bucket[key] = bucket.get(key, 0) + row["count"]
    return bucket


def _get_list_stats() -> dict[str, Any]:
    """
    Count reading lists: whose, where their issues come from, how many match.

    Counts only. A list's name, type and description, a source's reference
    and an entry's series name are free text or library names, so none is
    read here. The two data-keyed buckets are keyed by closed vocabularies:
    ``list_sources`` by the source kind, ``list_items`` by the item
    collection. ``personal_list_entry_count`` is the issues people put on
    their own lists one at a time, which an item's live entries are not.
    """
    personal = ReadingList.objects.filter(user__isnull=False)
    sources = ReadingListSource.objects
    list_items = _closed_bucket(
        sources.filter(kind=ReadingListSourceKind.COLLECTION),
        "collection",
        _ITEM_COLLECTION_KEYS,
    )
    entries = ReadingListEntry.objects
    return {
        "personal_list_count": personal.count(),
        "personal_list_user_count": personal.values("user").distinct().count(),
        "personal_list_entry_count": entries.filter(
            reading_list__user__isnull=False, live_source__isnull=True
        ).count(),
        "list_sources": _closed_bucket(sources.all(), "kind", _SOURCE_KIND_KEYS),
        "list_item_count": sum(list_items.values()),
        "list_items": list_items,
        "list_entry_count": entries.count(),
        "list_entry_missing_count": entries.filter(MISSING_Q).count(),
    }


def get_usage_stats() -> dict[str, Any]:
    """
    Report reader engagement: bookmarks, reading lists and API keys.

    Counts only; see :func:`_get_list_stats` for the lists. API keys are
    counted and nothing else: never a name, a prefix, a digest or a
    timestamp. "Used" is whether ``last_used_at`` is set, never its value.
    """
    device_keys = UserApiKey.objects.filter(scope=ApiKeyScope.DEVICE.value)
    universal_keys = UserApiKey.objects.filter(scope=ApiKeyScope.UNIVERSAL.value)
    return {
        "bookmark_count": Bookmark.objects.count(),
        **_get_list_stats(),
        "device_key_count": device_keys.count(),
        "device_key_user_count": device_keys.values("user").distinct().count(),
        "device_key_used_count": device_keys.filter(last_used_at__isnull=False).count(),
        "universal_key_used_count": universal_keys.filter(
            last_used_at__isnull=False
        ).count(),
    }


def _identifier_bucket_key(source: str | None, id_type: str | None) -> str:
    """Build a "source:id_type" key from closed vocabularies only."""
    name = (source or "").lower()
    if name not in IDENTIFIER_SOURCES:
        name = OTHER_IDENTIFIER_SOURCE
    kind = id_type if id_type in IdentifierType else OTHER_IDENTIFIER_SOURCE
    return f"{name}:{kind}"


def get_identifier_stats() -> dict[str, int]:
    """
    Count identifiers by source and type.

    The durable proxy for online tagging use: an issue identifier from
    metron or comicvine means that comic was matched against that service.
    """
    rows = (
        Identifier.objects.values("source__name", "id_type")
        .annotate(count=Count("pk"))
        .order_by()
    )
    buckets: dict[str, int] = {}
    for row in rows:
        key = _identifier_bucket_key(row["source__name"], row["id_type"])
        buckets[key] = buckets.get(key, 0) + row["count"]
    return dict(sorted(buckets.items()))


def get_multi_sort_count() -> int:
    """Count users who have added a secondary sort column in table view."""
    return SettingsBrowser.objects.exclude(order_extra_keys=[]).count()
