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

from codex.models import Comic, Folder, Imprint, Publisher, Series, Volume
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.views.browser_base import BrowserBaseView


class BrowserMetadataBaseView(BrowserBaseView):
    """Base class for views that need special metadata annotations."""

    _ORDER_BY_FIELD_ALIASES = {"search_score": "searchresult__score"}
    _ORDER_AGGREGATE_FUNCS = {
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "maturity_rating": Avg,
        "page_count": Sum,
        "size": Sum,
        "updated_at": Min,
        "user_rating": Avg,
        "searchresult__score": Min,
    }
    _NO_SEARCH_SCORE = Value(None, IntegerField())
    GROUP_MODEL_MAP = {
        "r": None,
        "p": Publisher,
        "i": Imprint,
        "s": Series,
        "v": Volume,
        BrowserBaseView.COMIC_GROUP: Comic,
        BrowserBaseView.FOLDER_GROUP: Folder,
    }
    DEFAULT_ORDER_KEY = "sort_name"

    def _annotate_cover_path(self, queryset, model):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the descendant comics by the sort argumentst
        if model == Comic:
            cover_path = F("cover_path")
        else:
            order_by, _ = self.get_order_by(model, for_cover_path=True)
            cover_path = Subquery(
                queryset.filter(pk=OuterRef("pk"))
                .order_by(*order_by)
                .values("comic__cover_path")[:1]
            )
        obj_list = queryset.annotate(**{f"{UNIONFIX_PREFIX}cover_path": cover_path})
        return obj_list

    def _annotate_page_count(self, obj_list):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        page_count_sum = Sum("comic__page_count")
        obj_list = obj_list.annotate(page_count=page_count_sum)
        return obj_list

    def _get_userbookmark_filter(self, is_model_comic):
        """Get a filter for my session or user defined bookmarks."""
        ubm_rel = self.get_ubm_rel(is_model_comic)

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{ubm_rel}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {
                f"{ubm_rel}__session__session_key": self.request.session.session_key
            }
        return Q(**my_bookmarks_kwargs)

    def _annotate_bookmarks(self, obj_list, is_model_comic):
        """Hoist up bookmark annoations."""
        ub_filter = self._get_userbookmark_filter(is_model_comic)

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
    def _annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from userbookmarks.
        # Requires page_count native to comic or aggregated
        queryset = queryset.annotate(
            progress=Coalesce(F("bookmark") * 100.0 / F("page_count"), 0.0)
        )
        return queryset

    def get_aggregate_func(self, field, is_comic_model, autoquery_pk=None):
        """Get a complete function for aggregating an attribute."""
        if field == "search_score":
            if not autoquery_pk:
                return self._NO_SEARCH_SCORE
            field = "searchresult__score"

        # get agg_func
        agg_func = self._ORDER_AGGREGATE_FUNCS.get(field)
        if agg_func == Min and self.params.get("order_reverse"):
            agg_func = Max

        # Determine order func
        if is_comic_model or agg_func is None:
            # agg_none uses group fields not comic fields.
            func = F(field)
        else:
            prefix = ""
            if not is_comic_model:
                prefix += "comic__"
            filters = Q(**{f"{prefix}searchresult__query": autoquery_pk})
            func = agg_func(prefix + field, filters=filters)
        return func

    def annotate_common_aggregates(self, qs, model):
        """Annotate common aggregates between browser and metadata."""
        is_model_comic = model == Comic
        qs = self._annotate_cover_path(qs, model)
        if not is_model_comic:
            qs = self._annotate_page_count(qs)
            child_count_sum = Count("comic__pk", distinct=True)
        else:
            child_count_sum = Value(1, IntegerField())
        qs = qs.annotate(child_count=child_count_sum)
        qs = self._annotate_bookmarks(qs, is_model_comic)
        qs = self._annotate_progress(qs)
        return qs

    def get_order_by(self, model, for_cover_path=False):
        """
        Create the order_by list.

        Order on pk to give duplicates a consistent position.
        """
        # order_keys
        order_key = ""
        if for_cover_path:
            order_key += "comic__"
            ok = self.params.get("order_by", self.DEFAULT_ORDER_KEY)
            ok = self._ORDER_BY_FIELD_ALIASES.get(ok, ok)
            order_key += ok
        else:
            order_key += "order_value"

        order_keys = [order_key, "sort_name", "pk"]

        # order_prefix
        order_reverse_prefix = "-" if self.params.get("order_reverse") else ""

        # order_by
        # add prefix to all order_by fields
        order_by = [
            order_reverse_prefix + field for field in (order_key, "sort_name", "pk")
        ]
        if model in (Comic, Folder):
            # This keeps position stability for duplicate comics & folders
            order_by += ["library"]

        return order_by, order_keys
