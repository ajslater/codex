"""
Age rating model, ordering, and ACL helpers.

``Unknown`` is intentionally absent from the ordered tuple: at filter time
it is treated the same as ``NULL`` (both inherit the ``AGE_RATING_DEFAULT``
admin flag). Admin-facing selects consume :data:`SELECTABLE_RATINGS` which
also excludes ``Unknown``.
"""

from typing import Final, override

from comicbox.enums.maps.age_rating import to_metron_age_rating
from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.db.models import IntegerField

from codex.models.base import MAX_NAME_LEN, NamedModel
from codex.models.fields import CleaningCharField

__all__ = ("AgeRating",)

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

# Sentinel index for ratings outside ``METRON_RATING_ORDER`` (``Unknown``, ``None``,
# and unrecognised names). Stored on :class:`AgeRating.metron_index` so SQL-only
# filtering can distinguish "ordered rating" rows from "treat as null" rows without
# a Python callout.
UNRANKED_METRON_INDEX: Final[int] = -1


def rating_index(rating: str | None) -> int:
    """Return the ordered index of a rating; -1 if not in ``METRON_RATING_ORDER``."""
    if rating in METRON_RATING_ORDER:
        return METRON_RATING_ORDER.index(rating)
    return UNRANKED_METRON_INDEX


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


def compute_metron_for_name(name: str | None) -> tuple[str, int]:
    """
    Compute ``(metron_name, metron_index)`` from an :class:`AgeRating.name`.

    - If ``name`` maps to a ranked Metron rating, returns that rating's value
      and its index in :data:`METRON_RATING_ORDER`.
    - If ``name`` maps to an unranked Metron rating (``Unknown``), returns the
      rating value with :data:`UNRANKED_METRON_INDEX`.
    - If ``name`` does not map (or is empty), returns ``("", UNRANKED_METRON_INDEX)``.
    """
    if not name:
        return "", UNRANKED_METRON_INDEX
    result = to_metron_age_rating(name)
    if result is None:
        return "", UNRANKED_METRON_INDEX
    metron_name = result.value
    return metron_name, rating_index(metron_name)


class AgeRating(NamedModel):
    """
    Age rating tagged on the comic file.

    ``metron_name`` and ``metron_index`` cache the normalized Metron rating
    derived from :attr:`name`; they are recomputed on every :meth:`presave`
    so callers can filter on the normalized value without rerunning the
    mapping in Python.
    """

    metron_name = CleaningCharField(
        db_index=True,
        max_length=MAX_NAME_LEN,
        default="",
        blank=True,
        db_collation="nocase",
    )
    metron_index = IntegerField(db_index=True, default=UNRANKED_METRON_INDEX)

    @override
    def presave(self) -> None:
        """Recompute the normalized Metron name/index from ``name``."""
        super().presave()
        self.metron_name, self.metron_index = compute_metron_for_name(self.name)
