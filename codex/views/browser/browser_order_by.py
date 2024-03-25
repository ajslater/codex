"""Base view for ordering the query."""

from os import sep
from types import MappingProxyType

from django.db.models import Avg, F, Max, Min, Sum, Value
from django.db.models.functions import Reverse, Right, StrIndex

from codex.models import Comic, Folder, StoryArc
from codex.views.browser.base import BrowserBaseView


class BrowserOrderByView(BrowserBaseView):
    """Base class for views that need ordering."""

    _ORDER_AGGREGATE_FUNCS = MappingProxyType(
        {
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
    )
    _SEP_VALUE = Value(sep)
    _ANNOTATED_ORDER_FIELDS = frozenset(
        ("sort_name", "search_score", "bookmark_updated_at")
    )
    _COMIC_COVER_ORDERING = ("comic__" + field for field in Comic.ORDERING)

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
            field,
            StrIndex(Reverse(field), cls._SEP_VALUE) - 1,  # type: ignore
        )

    def get_aggregate_func(self, model, field):
        """Order by aggregate."""
        # get agg_func
        agg_func = self._ORDER_AGGREGATE_FUNCS[field]
        if agg_func == Min and self.params.get("order_reverse"):
            agg_func = Max

        # get full_field
        self.kwargs.get("group")
        if model == StoryArc and field == "story_arc_number":
            full_field = "storyarcnumber__number"
        else:
            if self.order_key == "story_arc_number":
                field = "story_arc_numbers__number"
            full_field = self.rel_prefix + field
        if field == "path":
            full_field = self._get_path_query_func(full_field)

        return agg_func(full_field)

    def get_order_value(self, model):
        """Get a complete function for aggregating an attribute."""
        # Determine order func
        if self.order_key == "path" and model in (Comic, Folder):
            # special path sorting.
            func = self._get_path_query_func(self.order_key)
        elif model == Comic or self.order_key in self._ANNOTATED_ORDER_FIELDS:
            # agg_none uses group fields not comic fields.
            func = F(self.order_key)  # type: ignore
        else:
            func = self.get_aggregate_func(model, self.order_key)
        return func

    def add_order_by(self, queryset, model, cover=False):
        """Create the order_by list."""
        prefix = ""
        if self.params.get("order_reverse"):
            prefix += "-"

        if self.order_key == "sort_name":
            if cover and model != Comic:
                order_fields = self._COMIC_COVER_ORDERING
            else:
                order_fields = model.ORDERING
        elif self.order_key == "bookmark_updated_at":
            order_fields = ("order_value", "updated_at", "created_at", "pk")
        elif self.order_key == "story_arc_number" and model == Comic:
            order_fields = ("order_value", "date", *model.ORDERING)
        else:
            order_fields = ("order_value", *model.ORDERING)

        order_by = []
        for field in order_fields:
            order_by.append(prefix + field)

        return queryset.order_by(*order_by)
