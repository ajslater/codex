"""Comic field filters."""
from django.db.models import Q

from codex.views.session import BrowserSessionViewBase


class ComicFieldFilter(BrowserSessionViewBase):
    """Comic field filters."""

    def _filter_by_comic_field(self, field, is_model_comic):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(field)  # type: ignore
        filter_query = Q()
        if not filter_list:
            return filter_query
        if is_model_comic:
            query_prefix = ""
        else:
            query_prefix = "comic__"

        if field == self.CREDIT_PERSON_UI_FIELD:
            rel = f"{query_prefix}credits__person"
        else:
            rel = f"{query_prefix}{field}"

        for index, val in enumerate(filter_list):
            # None values in a list don't work right so test for them separately
            if val is None:
                del filter_list[index]
                filter_query |= Q(**{f"{rel}__isnull": True})
        if filter_list:
            filter_query |= Q(**{f"{rel}__in": filter_list})
        return filter_query

    def get_comic_field_filter(self, is_model_comic):
        """Filter the comics based on the form filters."""
        comic_field_filter = Q()
        for attribute in self.FILTER_ATTRIBUTES:
            comic_field_filter &= self._filter_by_comic_field(attribute, is_model_comic)
        return comic_field_filter
