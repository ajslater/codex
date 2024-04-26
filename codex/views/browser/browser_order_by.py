"""Base view for ordering the query."""

from django.db.models.aggregates import Max, Min

from codex.models import Comic
from codex.views.browser.filters.annotations import (
    BrowserAnnotationsFilterView,
)


class BrowserOrderByView(BrowserAnnotationsFilterView):
    """Base class for views that need ordering."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.order_key: str = ""

    def set_order_key(self):
        """Get the default order key for the view."""
        order_key: str = self.params.get("order_by", "")  # type: ignore
        if not order_key:
            group = self.kwargs.get("group")
            order_key = "filename" if group == self.FOLDER_GROUP else "sort_name"
        self.order_key: str = order_key
        order_reverse = self.params.get("order_reverse")
        self.order_agg_func = Max if order_reverse else Min

    def add_order_by(self, qs, model):
        """Create the order_by list."""
        order_fields_head = None
        if model == Comic:
            if self.order_key == "sort_name":
                order_fields_head = [
                    *self.comic_sort_names,  # type: ignore
                    "issue_number",
                    "issue_suffix",
                    "sort_name",
                ]
            else:
                # Comic orders on indexed fields directly
                # Which is allegedly faster than using tmp b-trees (annotations)
                # And since that's every cover sort, it's worth it.
                order_fields_head = [self.order_key]
                # Comic order micro optimizations
                if self.order_key == "story_arc_number":
                    order_fields_head += ["date"]
                elif self.order_key == "bookmark_updated_at":
                    order_fields_head += ["updated_at"]
        else:
            order_fields_head = ["order_value"]

        order_fields = (*order_fields_head, "pk")

        prefix = "-" if self.params.get("order_reverse") else ""
        order_by = []
        if prefix:
            for field in order_fields:
                order_by.append(prefix + field)
        else:
            order_by = order_fields

        return qs.order_by(*order_by)
