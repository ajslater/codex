"""Base view for metadata annotations."""
from django.db.models import (
    BooleanField,
    Case,
    Count,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.fields import PositiveSmallIntegerField
from django.db.models.functions import Least

from codex.models import Comic, Folder, Imprint, Publisher, Series, Volume
from codex.views.browser.base import BrowserBaseView
from codex.views.browser.browser_order_by import BrowserOrderByView


class BrowserAnnotationsView(BrowserOrderByView):
    """Base class for views that need special metadata annotations."""

    _ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
    # used by browser & metadata
    GROUP_MODEL_MAP = {
        BrowserBaseView.ROOT_GROUP: None,
        "p": Publisher,
        "i": Imprint,
        "s": Series,
        "v": Volume,
        BrowserBaseView.COMIC_GROUP: Comic,
        BrowserBaseView.FOLDER_GROUP: Folder,
    }

    def _annotate_search_score(self, queryset, is_model_comic, search_scores):
        """Annotate the search score for ordering by search score."""
        order_key = self.params.get("order_by")
        if order_key != "search_score":
            return queryset
        prefix = "comic__" if not is_model_comic else ""
        whens = []
        for pk, score in search_scores.items():
            when = {prefix + "pk": pk, "then": score}
            whens.append(When(**when))
        annotate = {prefix + "search_score": Case(*whens, default=0.0)}
        return queryset.annotate(**annotate)

    def _annotate_cover_pk(self, queryset, model):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the descendant comics by the sort argumentst
        if model == Comic:
            cover_pk = F("pk")
        else:
            # This creates two subqueries. It would be better condensed into one.
            # but there's no way to annotate an object or multiple values.
            qs = queryset.filter(pk=OuterRef("pk"))
            cover_comics = self.get_order_by(Comic, qs, for_cover_pk=True)
            cover_pk = Subquery(cover_comics.values("comic__pk")[:1])
        queryset = queryset.annotate(cover_pk=cover_pk)
        return queryset

    def _annotate_page_count(self, obj_list):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        page_count_sum = Sum("comic__page_count")
        obj_list = obj_list.annotate(page_count=page_count_sum)
        return obj_list

    def _annotate_bookmarks(self, obj_list, is_model_comic):
        """Hoist up bookmark annoations."""
        bm_rel = self.get_bm_rel(is_model_comic)
        bm_filter = self._get_my_bookmark_filter(bm_rel)

        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if is_model_comic:
            # Hoist up the bookmark and finished states
            bookmark_page = Sum(
                page_rel,
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            finished_aggregate = Sum(
                finished_rel,
                default=False,
                filter=bm_filter,
                output_field=BooleanField(),
            )
        else:
            # Aggregate bookmark and finished states
            bookmark_page = Sum(
                Case(
                    When(**{bm_rel: None}, then=0),
                    When(**{finished_rel: True}, then="comic__page_count"),
                    default=page_rel,
                    output_field=PositiveSmallIntegerField(),
                ),
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            finished_count = Sum(
                finished_rel,
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            obj_list = obj_list.annotate(finished_count=finished_count)
            finished_aggregate = Case(
                When(
                    Q(finished_count=F("child_count")) | Q(page=F("page_count")),
                    then=True,
                ),
                When(page=0, then=False),
                default=None,
                output_field=BooleanField(),
            )

        obj_list = obj_list.annotate(
            page=bookmark_page,
            finished=finished_aggregate,
        )

        return obj_list

    @staticmethod
    def _annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        then = Least(F("page") * 100.0 / F("page_count"), Value(100.0))
        progress = Case(When(page_count__gt=0, then=then), default=0.0)
        queryset = queryset.annotate(progress=progress)
        return queryset

    def annotate_common_aggregates(self, qs, model, search_scores):
        """Annotate common aggregates between browser and metadata."""
        is_model_comic = model == Comic
        qs = self._annotate_search_score(qs, is_model_comic, search_scores)
        qs = self._annotate_cover_pk(qs, model)
        if is_model_comic:
            child_count_sum = self._ONE_INTEGERFIELD
        else:
            qs = self._annotate_page_count(qs)
            child_count_sum = Count("comic__pk", distinct=True)
        qs = qs.annotate(child_count=child_count_sum)
        qs = self._annotate_bookmarks(qs, is_model_comic)
        qs = self._annotate_progress(qs)
        return qs
