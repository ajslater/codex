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
