"""Comic field filters."""

from types import MappingProxyType

from django.db.models import Q

from codex.models.comic import Comic
from codex.views.browser.filters.group import GroupFilterView

_FILTER_REL_MAP = MappingProxyType(
    {
        GroupFilterView.CONTRIBUTOR_PERSON_UI_FIELD: "contributors__person",
        GroupFilterView.STORY_ARC_UI_FIELD: "story_arc_numbers__story_arc",
        GroupFilterView.IDENTIFIER_TYPE_UI_FIELD: "identifiers__identifier_type",
    }
)


class ComicFieldFilterView(GroupFilterView):
    """Comic field filters."""

    def _filter_by_comic_field(self, field, rel_prefix):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(field)  # type: ignore
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

    def get_comic_field_filter(self, model):
        """Filter the comics based on the form filters."""
        comic_field_filter = Q()
        rel_prefix = "" if model == Comic else self.rel_prefix  # type: ignore
        for attribute in self.FILTER_ATTRIBUTES:
            comic_field_filter &= self._filter_by_comic_field(attribute, rel_prefix)
        return comic_field_filter
