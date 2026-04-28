"""
Age rating models, ordering, and ACL helpers.

:class:`AgeRating` is the raw tagged rating on each comic file (one row per
distinct tagged name). :class:`AgeRatingMetron` is the canonical Metron
enum table: a small, fully-seeded lookup whose rows are never deleted.
Each :class:`AgeRating` optionally points at one :class:`AgeRatingMetron`
row via :attr:`AgeRating.metron`; unmappable tagged names leave that FK
NULL.

``Unknown`` is intentionally absent from :data:`METRON_RATING_ORDER`: at
filter time it is treated the same as ``NULL`` (both inherit the
``AGE_RATING_DEFAULT`` admin flag). Admin-facing selects pull the live
:class:`AgeRatingMetron` list via the API, excluding ``Unknown`` server
side.
"""

from types import MappingProxyType
from typing import Final, override

from comicbox.enums.maps.age_rating import to_metron_age_rating
from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.db.models import SET_NULL, ForeignKey, IntegerField

from codex.models.base import NamedModel

__all__ = ("AgeRating", "AgeRatingMetron")

METRON_RATING_ORDER: Final[tuple[str, ...]] = (
    MetronAgeRatingEnum.EVERYONE.value,
    MetronAgeRatingEnum.TEEN.value,
    MetronAgeRatingEnum.TEEN_PLUS.value,
    MetronAgeRatingEnum.MATURE.value,
    MetronAgeRatingEnum.EXPLICIT.value,
    MetronAgeRatingEnum.ADULT.value,
)
# rating name → ordered index, materialized once. Replaces a
# ``in METRON_RATING_ORDER`` membership check followed by an
# ``.index()`` scan with a single dict lookup.
_RATING_INDEX: Final[MappingProxyType[str, int]] = MappingProxyType(
    {name: idx for idx, name in enumerate(METRON_RATING_ORDER)}
)

PUBLIC_TIER_ALLOWED: Final[frozenset[str]] = frozenset(
    {MetronAgeRatingEnum.EVERYONE.value}
)

UNKNOWN_VALUE: Final[str] = MetronAgeRatingEnum.UNKNOWN.value

# Seed / fallback for the ``AGE_RATING_DEFAULT`` admin flag. Governs how
# ``null``-rated and ``Unknown``-rated comics are treated at filter time:
# they inherit this rating, which is then compared against the viewing
# user's ceiling. ``Everyone`` is the safest choice — null/unknown
# comics only reach users whose ceiling also includes ``Everyone`` (i.e.
# everyone, by definition).
DEFAULT_AGE_RATING: Final[str] = MetronAgeRatingEnum.EVERYONE.value

# Seed / fallback for the ``ANONYMOUS_USER_AGE_RATING`` admin flag. Governs
# the ceiling applied when the request has no authenticated user.
# ``Adult`` here means out-of-the-box anonymous browsing sees the full
# library; admins restrict it by changing the flag.
ANONYMOUS_USER_DEFAULT_AGE_RATING: Final[str] = MetronAgeRatingEnum.ADULT.value

# Sentinel ceiling used by the auth filter when a user has no rating
# restriction (``UserAuth.age_rating_metron`` is ``NULL``). Any ranked
# :attr:`AgeRatingMetron.index` (0..5) compares ``<=`` this value, so the
# ACL filter becomes a trivial pass-through for unrestricted users without
# branching in Python.
UNRESTRICTED_RATING_INDEX: Final[int] = 999

# Sentinel index for ratings outside ``METRON_RATING_ORDER`` (``Unknown``).
# Stored on :class:`AgeRatingMetron.index` so SQL-only filtering can
# distinguish "ranked rating" rows from "treat as null" rows without a
# Python callout.
UNRANKED_METRON_INDEX: Final[int] = -1

# The full seed set for :class:`AgeRatingMetron`: every
# :class:`MetronAgeRatingEnum` value paired with its sort index. ``Unknown``
# gets the sentinel :data:`UNRANKED_METRON_INDEX`; ranked ratings get their
# position in :data:`METRON_RATING_ORDER`. Consumed by the migration and
# the startup seeder.
ALL_METRON_RATINGS: Final[tuple[tuple[str, int], ...]] = (
    (UNKNOWN_VALUE, UNRANKED_METRON_INDEX),
    *((name, idx) for idx, name in enumerate(METRON_RATING_ORDER)),
)

# Process-lifetime cache of :attr:`AgeRatingMetron.pk` → :attr:`index`.
# The seed table has 7 rows whose indexes are sealed at module load via
# :data:`METRON_RATING_ORDER`, so the mapping is effectively static once
# populated. Rebuilt lazily on first lookup and cleared by
# :func:`invalidate_metron_index_cache` whenever the seed is re-asserted
# (startup or test teardown).
_METRON_INDEX_BY_PK: dict[int, int] = {}


def get_metron_index(metron_id: int | None) -> int | None:
    """
    Return the :attr:`AgeRatingMetron.index` for ``metron_id``.

    Used by :meth:`Comic.presave` to populate the denormalized
    :attr:`Comic.age_rating_metron_index` column without firing a per-row
    query in the bulk import path. ``None`` means either the comic has
    no linked metron row or the pk is missing from the cached map
    (treated identically by the ACL filter).
    """
    if metron_id is None:
        return None
    if not _METRON_INDEX_BY_PK:
        _METRON_INDEX_BY_PK.update(AgeRatingMetron.objects.values_list("pk", "index"))
    return _METRON_INDEX_BY_PK.get(metron_id)


def invalidate_metron_index_cache() -> None:
    """Drop the cached pk → index map; next lookup re-populates from DB."""
    _METRON_INDEX_BY_PK.clear()


def rating_index(rating: str | None) -> int:
    """Return the ordered index of a rating; -1 if not in ``METRON_RATING_ORDER``."""
    return (
        _RATING_INDEX.get(rating, UNRANKED_METRON_INDEX)
        if rating
        else UNRANKED_METRON_INDEX
    )


def allowed_ratings_for(group_rating: str | None) -> frozenset[str]:
    """
    Return the allowed rating set for one group rating.

    An empty frozenset indicates no restriction (caller should treat as
    unrestricted). Values outside :data:`METRON_RATING_ORDER` (``Unknown``
    or ``None``) also produce an empty set.
    """
    idx = rating_index(group_rating)
    if idx < 0:
        return frozenset()
    return frozenset(METRON_RATING_ORDER[: idx + 1])


def compute_metron_for_name(name: str | None) -> str:
    """
    Map an :class:`AgeRating.name` to its canonical Metron rating name.

    Returns the empty string when ``name`` is empty or doesn't map to any
    :class:`MetronAgeRatingEnum` value. Callers that need to look up an
    :class:`AgeRatingMetron` row should treat an empty return as "no
    matching row".
    """
    if not name:
        return ""
    result = to_metron_age_rating(name)
    if result is None:
        return ""
    return result.value


class AgeRatingMetron(NamedModel):
    """
    Canonical Metron age rating — a fixed lookup table.

    Rows correspond 1:1 with :class:`MetronAgeRatingEnum` values. Fully
    seeded by migration and re-asserted on every codex startup; never
    deleted. :attr:`AgeRating.metron` points here for each tagged rating
    that maps to a canonical value.

    :attr:`index` mirrors the position in :data:`METRON_RATING_ORDER`
    (``Everyone``=0 … ``Adult``=5). ``Unknown`` stores
    :data:`UNRANKED_METRON_INDEX` (-1).
    """

    index = IntegerField(db_index=True, default=UNRANKED_METRON_INDEX)

    class Meta(NamedModel.Meta):
        """Order choices by enum index so UI ordering falls out for free."""

        ordering = ("index",)


class AgeRating(NamedModel):
    """
    Age rating tagged on the comic file.

    :attr:`metron` caches the normalized :class:`AgeRatingMetron` row
    derived from :attr:`name`; it is relinked on every :meth:`presave`
    so callers can filter on the normalized value without rerunning the
    mapping in Python. Unmappable names leave :attr:`metron` NULL.
    """

    metron = ForeignKey(
        AgeRatingMetron,
        db_index=True,
        null=True,
        blank=True,
        default=None,
        on_delete=SET_NULL,
    )

    @override
    def presave(self) -> None:
        """Relink :attr:`metron` to the :class:`AgeRatingMetron` row for :attr:`name`."""
        super().presave()
        metron_name = compute_metron_for_name(self.name)
        if not metron_name:
            self.metron = None
            return
        # AgeRatingMetron is seeded at migration + startup, so this lookup
        # is a cache-friendly indexed hit. First-time seeding gaps would
        # null the FK (re-imports heal once the seeder catches up).
        self.metron = AgeRatingMetron.objects.filter(name=metron_name).first()
