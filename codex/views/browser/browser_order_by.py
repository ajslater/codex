"""Base view for ordering the query."""
from os import sep

from django.db.models import Avg, F, Max, Min, Sum, Value
from django.db.models.functions import Reverse, Right, StrIndex

from codex.models import Comic, Folder
from codex.views.browser.base import BrowserBaseView


class BrowserOrderByView(BrowserBaseView):
    """Base class for views that need ordering."""

    _ORDER_AGGREGATE_FUNCS = {
        "age_rating": Avg,
        "community_rating": Avg,
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "page_count": Sum,
        "path": Min,
        "size": Sum,
        "updated_at": Min,
        "search_score": Min,
        "story_arc_number": Min,
    }
    _SEP_VALUE = Value(sep)
    _ORDER_FIELDS = ("order_value", "pk")

    def set_order_key(self):
        """Get the default order key for the view."""
        order_key = self.params.get("order_by")
        if not order_key:
            group = self.kwargs.get("group")
            order_key = "path" if group == self.FOLDER_GROUP else "sort_name"
        self.order_key = order_key

    @classmethod
    def _get_path_query_func(cls, field):
        """Use the db to get only the filename."""
        return Right(
            field, StrIndex(Reverse(field), cls._SEP_VALUE) - 1  # type: ignore
        )

    def get_aggregate_func(self, field):
        """Order by aggregate."""
        # get agg_func
        agg_func = self._ORDER_AGGREGATE_FUNCS[field]
        if agg_func == Min and self.params.get("order_reverse"):
            agg_func = Max

        # get full_field
        full_field = "comic__" + field
        if field == "path":
            full_field = self._get_path_query_func(full_field)

        return agg_func(full_field)

    def get_order_value(self, model):
        """Get a complete function for aggregating an attribute."""
        # Determine order func
        if self.order_key == "path" and model in (Comic, Folder):
            # special path sorting.
            func = self._get_path_query_func(self.order_key)
        elif model == Comic or self.order_key in ("sort_name", "bookmark_updated_at"):
            # agg_none uses group fields not comic fields.
            func = F(self.order_key)
        else:
            func = self.get_aggregate_func(self.order_key)
        return func

    def add_order_by(self, queryset, model, for_cover=False):
        """Create the order_by list."""
        prefix = ""
        if self.params.get("order_reverse"):
            prefix += "-"

        if for_cover:
            prefix += "comic__"
            # Cover Comic subquery has no order_value or sort_name
            if self.order_key == "sort_name":
                order_fields = Comic.ORDERING
            else:
                order_fields = (self.order_key, "pk")
        else:
            if self.order_key == "sort_name":  # noqa PLR5501
                order_fields = (self._ORDER_FIELDS[0], *model.ORDERING[1:])
            else:
                order_fields = self._ORDER_FIELDS

        order_by = []
        for field in order_fields:
            order_by.append(prefix + field)

        return queryset.order_by(*order_by)
