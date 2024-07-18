"""Base view for ordering the query."""

from django.db.models.aggregates import Max, Min

from codex.models import Comic
from codex.views.browser.filters.annotations import (
    BrowserAnnotationsFilterView,
)


class BrowserOrderByView(BrowserAnnotationsFilterView):
    """Base class for views that need ordering."""

    def set_order_key(self):
        """Get the default order key for the view."""
        self.order_key: str = self.params["order_by"]
        order_reverse = self.params.get("order_reverse")
        self.order_agg_func = Max if order_reverse else Min

    def _add_comic_order_by(self, order_key, comic_sort_names):
        """Order by for comics (and covers)."""
        if not order_key:
            order_key = self.order_key
        if order_key == "sort_name":
            if not comic_sort_names:
                comic_sort_names = self.comic_sort_names  # type: ignore
            order_fields_head = [
                *comic_sort_names,
                "issue_number",
                "issue_suffix",
                "sort_name",
            ]
        else:
            # Comic orders on indexed fields directly
            # Which is allegedly faster than using tmp b-trees (annotations)
            # And since that's every cover sort, it's worth it.
            order_fields_head = [order_key]
            # Comic order micro optimizations
            if order_key == "story_arc_number":
                order_fields_head += ["date"]
            elif order_key == "bookmark_updated_at":
                order_fields_head += ["updated_at"]
        return order_fields_head

    def add_order_by(
        self, qs, model, order_key="", do_reverse=True, comic_sort_names=None
    ):
        """Create the order_by list."""
        order_fields_head = ()
        if model == Comic:
            order_fields_head = self._add_comic_order_by(order_key, comic_sort_names)
        else:
            order_fields_head = ["order_value"]

        order_fields = (*order_fields_head, "pk")

        prefix = "-" if do_reverse and self.params.get("order_reverse") else ""
        order_by = []
        if prefix:
            for field in order_fields:
                order_by.append(prefix + field)
        else:
            order_by = order_fields

        return qs.order_by(*order_by)
