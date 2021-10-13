"""Base view for metadata annotations."""
from decimal import Decimal

from django.db.models import (
    Avg,
    BooleanField,
    DecimalField,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Cast, Coalesce, NullIf

from codex.models import Comic, Folder
from codex.views.browser_base import BrowserBaseView


class BrowserMetadataBase(BrowserBaseView):
    """Base class for views that need special metadata annotations."""

    # options from frontend/src/choices/browserChoices.json
    SORT_AGGREGATE_FUNCS = {
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "maturity_rating": Avg,
        "page_count": Sum,
        "size": Sum,
        "updated_at": Min,
        "user_rating": Avg,
    }
    DEFAULT_ORDER_KEY = "sort_name"

    def get_aggregate_func(self, field, model, aggregate_filter):
        """Get a complete function for aggregating an attribute."""
        agg_func = self.SORT_AGGREGATE_FUNCS.get(field)
        if agg_func == Min:
            sort_reverse = self.params.get("sort_reverse")
            if sort_reverse:
                agg_func = Max
        if model == Comic or agg_func is None:
            order_func = F(field)
        else:
            order_func = agg_func(f"comic__{field}", filter=aggregate_filter)
        return order_func

    def get_order_by(self, model, use_order_value):
        """
        Create the order_by list.

        Order on pk to give duplicates a consistant position.
        """
        sort_reverse = self.params.get("sort_reverse")
        if sort_reverse:
            order_prefix = "-"
        else:
            order_prefix = ""
        if use_order_value:
            order_key = "order_value"
        else:
            order_key = self.params.get("sort_by")
        order_by = [order_prefix + order_key, order_prefix + "pk"]
        if model in (Comic, Folder):
            # This keeps position stability for duplicate comics & folders
            order_by += ["library"]
        return order_by

    def annotate_cover_path(self, queryset, model, aggregate_filter):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the decendent comics by the sort argumentst
        if model == Comic:
            cover_path_subquery = F("cover_path")
        else:
            # Cover Path from sorted children.
            # Don't know how to make this a join because it selects by
            #   order_by but wants the cover_path
            model_ref = model.__name__.lower()
            model_group_filter = Q(**{model_ref: OuterRef("pk")})
            comics = Comic.objects.filter(model_group_filter & aggregate_filter)
            order_by = self.get_order_by(Comic, False)
            comics = comics.order_by(*order_by)
            cover_comic_path = comics.values("cover_path")
            cover_path_subquery = Subquery(cover_comic_path[:1])
        obj_list = queryset.annotate(x_cover_path=cover_path_subquery)
        return obj_list

    def annotate_page_count(self, obj_list, aggregate_filter):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        page_count_sum = Sum("comic__page_count", filter=aggregate_filter)
        obj_list = obj_list.annotate(x_page_count=page_count_sum)
        return obj_list

    def get_userbookmark_filter(self, for_comic=False):
        """Get a filter for my session or user defined bookmarks."""
        rel_to_ub = "userbookmark"
        if not for_comic:
            rel_to_ub = "comic__userbookmark"

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{rel_to_ub}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {
                f"{rel_to_ub}__session__session_key": self.request.session.session_key
            }
        return Q(**my_bookmarks_kwargs)

    def annotate_bookmarks(self, obj_list):
        """Hoist up bookmark annoations."""
        ub_filter = self.get_userbookmark_filter()

        # Hoist up: are the children finished or unfinished?
        finished_aggregate = Cast(
            NullIf(
                Coalesce(
                    Avg(  # distinct average of user's finished values
                        "comic__userbookmark__finished",
                        filter=ub_filter,
                        distinct=True,
                        output_field=DecimalField(),
                    ),
                    False,  # Null db values counted as False
                ),
                Value(0.5),  # Null result if mixed true & false
            ),
            BooleanField(),  # Finally ends up as a ternary boolean
        )

        # Hoist up the bookmark
        bookmark_sum = Sum("comic__userbookmark__bookmark", filter=ub_filter)

        obj_list = obj_list.annotate(finished=finished_aggregate, bookmark=bookmark_sum)

        return obj_list

    @staticmethod
    def annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from userbookmarks.
        # Requires x_page_count native to comic or aggregated
        queryset = queryset.annotate(
            progress=Coalesce(
                F("bookmark") * Decimal("1.0") / F("x_page_count") * 100,
                Value(0.00),
                output_field=DecimalField(),
            )
        )
        return queryset
