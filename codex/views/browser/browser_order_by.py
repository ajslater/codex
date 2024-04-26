"""Base view for ordering the query."""

from os import sep
from types import MappingProxyType

from django.db.models import Avg, F, Max, Min, Sum, Value
from django.db.models.fields import CharField
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
            "filename": Min,
            "page_count": Sum,
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

    def set_order_key(self):
        """Get the default order key for the view."""
        order_key: str = self.params.get("order_by", "")  # type: ignore
        if not order_key:
            group = self.kwargs.get("group")
            order_key = "filename" if group == self.FOLDER_GROUP else "sort_name"
        self.order_key: str = order_key

    def _filename_from_path(self, model):
        """Calculate filename from path in the db."""
        path_rel = "path" if model == Comic else self.rel_prefix + "path"
        return Right(
            path_rel,
            StrIndex(Reverse(F(path_rel)), Value(sep)) - 1,  # type: ignore
            output_field=CharField(),
        )

    def get_aggregate_func(self, model, field):
        """Order by aggregate."""
        # get agg_func
        agg_func = self._ORDER_AGGREGATE_FUNCS[field]
        if agg_func == Min and self.params.get("order_reverse"):
            agg_func = Max

        # get full_field
        if model == StoryArc and field == "story_arc_number":
            full_field = "storyarcnumber__number"
        elif field == "filename":
            full_field = self._filename_from_path(model)
        else:
            if self.order_key == "story_arc_number":
                field = "story_arc_numbers__number"
            full_field = self.rel_prefix + field

        return agg_func(full_field)

    def get_order_value(self, model):
        """Get a complete function for aggregating an attribute."""
        # Determine order func
        if model == Comic or self.order_key in self._ANNOTATED_ORDER_FIELDS:
            # agg_none uses group fields not comic fields.
            if self.order_key == "filename":
                # no aggregation
                func = self._filename_from_path(model)
            else:
                # TODO most ANNOTATED_ORDER fields should be moved in here for ordering only
                #    But search_score is a filter
                #    sort_name is actutally only used for order.
                #    bookmark_updated_at is only used for order.
                func = F(self.order_key)
        elif model == Folder and self.order_key == "filename":
            return F("sort_name")
        else:
            func = self.get_aggregate_func(model, self.order_key)
        return func

    def add_order_by(self, qs, model):
        """Create the order_by list."""
        order_fields_head = None
        if model == Comic:
            if self.order_key == "sort_name":
                valid_nav_groups = self.valid_nav_groups  # type: ignore
                group = self.kwargs.get("group")
                order_fields_head = model.get_order_by(
                    valid_nav_groups, browser_group=group
                )
            elif self.order_key == "story_arc_number":
                order_fields_head = ("order_value", "date")
            elif self.order_key == "bookmark_updated_at":
                order_fields_head = (
                    "order_value",
                    "updated_at",
                )

        if not order_fields_head:
            order_fields_head = ("order_value",)

        order_fields = (*order_fields_head, "pk")

        prefix = "-" if self.params.get("order_reverse") else ""
        order_by = tuple(prefix + field for field in order_fields)

        return qs.order_by(*order_by)
