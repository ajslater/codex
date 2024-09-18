"""Comic field filters."""

from types import MappingProxyType

from django.db.models import Q

from codex.views.browser.filters.group import GroupFilterView
from codex.views.session import (
    CONTRIBUTOR_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
    STORY_ARC_UI_FIELD,
)

_FILTER_REL_MAP = MappingProxyType(
    {
        CONTRIBUTOR_PERSON_UI_FIELD: "contributors__person",
        STORY_ARC_UI_FIELD: "story_arc_numbers__story_arc",
        IDENTIFIER_TYPE_UI_FIELD: "identifiers__identifier_type",
    }
)


class ComicFieldFilterView(GroupFilterView):
    """Comic field filters."""

    @staticmethod
    def _filter_by_comic_field(field, rel_prefix, filter_list):
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
    def get_all_comic_field_filters(cls, rel_prefix, filters):
        """Get all comicfiled filters for rel_prefix."""
        comic_field_filter = Q()
        for field in cls.FILTER_ATTRIBUTES:
            filter_list = filters.get(field, [])
            comic_field_filter &= cls._filter_by_comic_field(
                field, rel_prefix, filter_list
            )
        return comic_field_filter

    def get_comic_field_filter(self, model):
        """Filter the comics based on the form filters."""
        rel_prefix = self.get_rel_prefix(model)
        filters = self.params["filters"]  # type: ignore
        return self.get_all_comic_field_filters(rel_prefix, filters)
