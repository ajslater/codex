"""
Metron age-rating ordering and ACL helpers.

``Unknown`` is intentionally absent from the ordered tuple: at filter time
it is treated the same as ``NULL`` (both inherit the ``AGE_RATING_DEFAULT``
admin flag). Admin-facing selects consume :data:`SELECTABLE_RATINGS` which
also excludes ``Unknown``.
"""

from typing import Final

from comicbox.enums.metroninfo import MetronAgeRatingEnum

METRON_RATING_ORDER: Final[tuple[str, ...]] = (
    MetronAgeRatingEnum.EVERYONE.value,
    MetronAgeRatingEnum.TEEN.value,
    MetronAgeRatingEnum.TEEN_PLUS.value,
    MetronAgeRatingEnum.MATURE.value,
    MetronAgeRatingEnum.EXPLICIT.value,
    MetronAgeRatingEnum.ADULT.value,
)

# Ratings offered in admin-facing selects (Group dialog, Flags tab default).
SELECTABLE_RATINGS: Final[tuple[str, ...]] = METRON_RATING_ORDER

PUBLIC_TIER_ALLOWED: Final[frozenset[str]] = frozenset(
    {MetronAgeRatingEnum.EVERYONE.value}
)

UNKNOWN_VALUE: Final[str] = MetronAgeRatingEnum.UNKNOWN.value

DEFAULT_AGE_RATING: Final[str] = MetronAgeRatingEnum.ADULT.value


def rating_index(rating: str | None) -> int:
    """Return the ordered index of a rating; -1 if not in ``METRON_RATING_ORDER``."""
    if rating in METRON_RATING_ORDER:
        return METRON_RATING_ORDER.index(rating)
    return -1


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
