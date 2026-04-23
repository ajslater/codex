"""Comic field filters."""

from types import MappingProxyType

from django.db.models.query_utils import Q

from codex.views.browser.const import BROWSER_FILTER_KEYS
from codex.views.browser.filters.group import GroupFilterView
from codex.views.settings import (
    CREDIT_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
    STORY_ARC_UI_FIELD,
)

_FILTER_REL_MAP = MappingProxyType(
    {
        CREDIT_PERSON_UI_FIELD: "credits__person",
        STORY_ARC_UI_FIELD: "story_arc_numbers__story_arc",
        IDENTIFIER_TYPE_UI_FIELD: "identifiers__source",
        # Both age-rating filters route through the ``Comic.age_rating`` FK.
        # The tagged filter uses :class:`AgeRating` PKs (matching the tagged
        # name); the metron filter uses :class:`AgeRatingMetron` PKs reached
        # via the ``age_rating__metron`` chain.
        "age_rating_tagged": "age_rating",
        "age_rating_metron": "age_rating__metron",
    }
)
_FILTER_ATTRIBUTES: frozenset[str] = frozenset(BROWSER_FILTER_KEYS)


class ComicFieldFilterView(GroupFilterView):
    """Comic field filters."""

    @staticmethod
    def _filter_by_comic_field(field, rel_prefix, filter_list) -> Q:
        """Filter by a comic any2many attribute."""
        filter_query = Q()
        if not filter_list:
            return filter_query

        rel = rel_prefix + _FILTER_REL_MAP.get(field, field)

        for index, val in enumerate(filter_list):
            # None values in a list don't work right so test for them separately
            if val is None:
                del filter_list[index]
                filter_query |= Q(**{f"{rel}__isnull": True})
        if filter_list:
            filter_query |= Q(**{f"{rel}__in": filter_list})
        return filter_query

    @classmethod
    def get_all_comic_field_filters(cls, rel_prefix, filters) -> Q:
        """Get all comicfiled filters for rel_prefix."""
        comic_field_filter = Q()
        # Only walk keys that are both valid AND set in this request's
        # filters - saves ~20 no-op `_filter_by_comic_field` calls per
        # request on typical browsers that set 0-2 field filters.
        for field in _FILTER_ATTRIBUTES & filters.keys():
            filter_list = filters.get(field)
            if not filter_list:
                continue
            comic_field_filter &= cls._filter_by_comic_field(
                field, rel_prefix, filter_list
            )
        return comic_field_filter

    def get_comic_field_filter(self, model) -> Q:
        """Filter the comics based on the form filters."""
        rel_prefix = self.get_rel_prefix(model)
        filters = self.params["filters"]
        return self.get_all_comic_field_filters(rel_prefix, filters)
