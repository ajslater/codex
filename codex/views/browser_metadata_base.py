"""Base view for metadata annotations."""
from django.db.models import (
    Avg,
    BooleanField,
    Count,
    DecimalField,
    F,
    IntegerField,
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
from codex.serializers.mixins import UNIONFIX_PREFIX
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

    def get_aggregate_func(self, field, is_comic_model):
        """Get a complete function for aggregating an attribute."""
        agg_func = self.SORT_AGGREGATE_FUNCS.get(field)
        if agg_func == Min:
            sort_reverse = self.params.get("sort_reverse")
            if sort_reverse:
                agg_func = Max
        if is_comic_model or agg_func is None:
            order_func = F(field)
        else:
            order_func = agg_func(f"comic__{field}")
        return order_func

    def get_order_by(self, model, use_order_value, for_cover_path=False):
        """
        Create the order_by list.

        Order on pk to give duplicates a consistent position.
        """
        # order_prefix
        sort_reverse = self.params.get("sort_reverse")
        if sort_reverse:
            order_prefix = "-"
        else:
            order_prefix = ""

        order_key = ""
        if for_cover_path:
            order_key += "comic__"

        # order_key
        if use_order_value:
            order_key += "order_value"
        else:
            order_key += self.params.get("sort_by", self.DEFAULT_ORDER_KEY)

        order_keys = [order_key, "pk"]
        order_by = [order_prefix + order_key, order_prefix + "pk"]
        if model in (Comic, Folder):
            # This keeps position stability for duplicate comics & folders
            order_by += ["library"]
        return order_by, order_keys

    def annotate_cover_path(self, queryset, model):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the descendant comics by the sort argumentst
        if model == Comic:
            cover_path = F("cover_path")
        else:
            order_by, _ = self.get_order_by(model, False, True)
            cover_path = Subquery(
                queryset.filter(pk=OuterRef("pk"))
                .order_by(*order_by)
                .values("comic__cover_path")[:1]
            )
        obj_list = queryset.annotate(**{f"{UNIONFIX_PREFIX}cover_path": cover_path})
        return obj_list

    def annotate_page_count(self, obj_list):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        page_count_sum = Sum("comic__page_count")
        obj_list = obj_list.annotate(page_count=page_count_sum)
        return obj_list

    def get_userbookmark_filter(self, is_model_comic):
        """Get a filter for my session or user defined bookmarks."""
        ubm_rel = self.get_ubm_rel(is_model_comic)

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{ubm_rel}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {
                f"{ubm_rel}__session__session_key": self.request.session.session_key
            }
        return Q(**my_bookmarks_kwargs)

    def annotate_bookmarks(self, obj_list, is_model_comic):
        """Hoist up bookmark annoations."""
        ub_filter = self.get_userbookmark_filter(is_model_comic)

        ubm_rel = self.get_ubm_rel(is_model_comic)

        # Hoist up: are the children finished or unfinished?
        finished_aggregate = Cast(
            NullIf(
                Coalesce(
                    Avg(  # distinct average of user's finished values
                        f"{ubm_rel}__finished",
                        filter=ub_filter,
                        distinct=True,
                        output_field=DecimalField(max_digits=2, decimal_places=2),
                    ),
                    False,  # Null db values counted as False
                ),
                Value(0.5),  # Null result if mixed true & false
            ),
            BooleanField(),  # Finally ends up as a ternary boolean
        )

        # Hoist up the bookmark
        bookmark_sum = Sum(f"{ubm_rel}__bookmark", filter=ub_filter)

        obj_list = obj_list.annotate(finished=finished_aggregate, bookmark=bookmark_sum)

        return obj_list

    @staticmethod
    def annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from userbookmarks.
        # Requires page_count native to comic or aggregated
        queryset = queryset.annotate(
            progress=Coalesce(F("bookmark") * 100.0 / F("page_count"), 0.0)
        )
        return queryset

    def annotate_common_aggregates(self, qs, model):
        """Annotate common aggregates between browser and metadata."""
        is_model_comic = model == Comic
        qs = self.annotate_cover_path(qs, model)
        if not is_model_comic:
            qs = self.annotate_page_count(qs)
            child_count_sum = Count("comic__pk", distinct=True)
        else:
            child_count_sum = Value(1, IntegerField())
        qs = qs.annotate(child_count=child_count_sum)
        qs = self.annotate_bookmarks(qs, is_model_comic)
        qs = self.annotate_progress(qs)
        return qs
