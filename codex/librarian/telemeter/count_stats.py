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

from codex.models.bookmark import Bookmark
from codex.models.comic import Comic
from codex.models.favorite import Favorite
from codex.models.identifier import Identifier, IdentifierType
from codex.models.library import Library
from codex.models.named import Credit, Reprint
from codex.models.paths import CustomCover, FailedImport
from codex.models.settings import SettingsBrowser

OTHER_IDENTIFIER_SOURCE: Final = "other"
# comicbox's closed source vocabulary. A source name read from a comic file
# that isn't in here is collapsed to "other" before it leaves the process.
IDENTIFIER_SOURCES: Final = frozenset(source.value for source in ID_SOURCE_NAME_MAP)
_ID_TYPES: Final = frozenset(member.value for member in IdentifierType)

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


def get_usage_stats() -> dict[str, Any]:
    """Report reader engagement: bookmarks and favorites."""
    favorites = Favorite.objects
    rows = favorites.values("collection").annotate(count=Count("pk")).order_by()
    return {
        "bookmark_count": Bookmark.objects.count(),
        "favorite_count": favorites.count(),
        "favorite_user_count": favorites.values("user").distinct().count(),
        "favorites": {row["collection"]: row["count"] for row in rows},
    }


def _identifier_bucket_key(source: str | None, id_type: str | None) -> str:
    """Build a "source:id_type" key from closed vocabularies only."""
    name = (source or "").lower()
    if name not in IDENTIFIER_SOURCES:
        name = OTHER_IDENTIFIER_SOURCE
    kind = id_type if id_type in _ID_TYPES else OTHER_IDENTIFIER_SOURCE
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
