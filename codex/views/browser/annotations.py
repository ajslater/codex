"""Base view for metadata annotations."""

from os import sep
from types import MappingProxyType

from django.db.models import (
    Avg,
    Case,
    F,
    FilteredRelation,
    Min,
    OuterRef,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.expressions import Subquery
from django.db.models.fields import CharField, PositiveSmallIntegerField
from django.db.models.functions import Least, Reverse, Right, StrIndex
from django.db.models.functions.comparison import Coalesce

from codex.logger.logging import get_logger
from codex.models import (
    BrowserGroupModel,
    Comic,
    Folder,
    StoryArc,
    Volume,
)
from codex.models.functions import ComicFTSRank, JsonGroupArray
from codex.models.groups import Imprint, Publisher, Series
from codex.views.browser.order_by import (
    BrowserOrderByView,
)
from codex.views.const import (
    NONE_DATETIMEFIELD,
    NONE_INTEGERFIELD,
    STORY_ARC_GROUP,
)
from codex.views.mixins import SharedAnnotationsMixin

_ORDER_AGGREGATE_FUNCS = MappingProxyType(
    # These are annotated to order_value because they're simple relations
    {
        "age_rating": Avg,
        "community_rating": Avg,
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "page_count": Sum,
        "size": Sum,
        "updated_at": Min,
    }
)
_ANNOTATED_ORDER_FIELDS = frozenset(
    # These are annotated with their own functions
    {
        "filename",
        "sort_name",
        "search_score",
        "bookmark_updated_at",
        "story_arc_number",
    }
)
_GROUP_BY: MappingProxyType[type[BrowserGroupModel], str] = MappingProxyType(
    {Publisher: "sort_name", Imprint: "sort_name", Series: "sort_name", Volume: "name"}
)

LOG = get_logger(__name__)


class BrowserAnnotationsView(BrowserOrderByView, SharedAnnotationsMixin):
    """Base class for views that need special metadata annotations."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.is_opds_1_acquisition = False
        self.comic_sort_names = ()
        self.bm_annotataion_data: dict[BrowserGroupModel, tuple[str, dict]] = {}

    def add_group_by(self, qs, model=None):
        """Get the group by for the model."""
        if model is None:
            model = self.model
        if group_by := _GROUP_BY.get(model):  # type: ignore
            qs = qs.group_by(group_by)
        return qs

    def _alias_sort_names(self, qs, model):
        """Annotate sort_name."""
        if self.order_key != "sort_name" and not (
            model == StoryArc and self.order_key == "story_arc_number"
        ):
            return qs
        pks = self.kwargs.get("pks")
        model_group = self.model_group  # type: ignore
        show = MappingProxyType(self.params["show"])  # type: ignore
        qs, self.comic_sort_names = self.alias_sort_names(
            qs, model, pks, model_group, show
        )
        return qs

    def _alias_filename(self, qs, model):
        """Calculate filename from path in the db."""
        if self.order_key != "filename":
            return qs
        if model == Folder:
            filename = F("name")
        else:
            prefix = "" if model == Comic else self.rel_prefix
            path_rel = prefix + "path"
            filename = self.order_agg_func(
                Right(
                    path_rel,
                    StrIndex(Reverse(F(path_rel)), Value(sep)) - 1,  # type: ignore
                    output_field=CharField(),
                )
            )
        return qs.alias(filename=filename)

    def _alias_story_arc_number(self, qs):
        if self.order_key != "story_arc_number":
            return qs

        # Get story_arc__pk
        group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        if group == STORY_ARC_GROUP and pks:
            story_arc_pks = pks
        else:
            story_arc_pks = self.params.get("filters", {}).get(  # type: ignore
                "story_arcs", ()
            )

        # If we have one annotate it.
        if story_arc_pks:
            san_rel = self.rel_prefix + "story_arc_numbers"
            rel = f"{san_rel}"
            condition = Q(**{f"{san_rel}__story_arc__in": story_arc_pks})
            qs = qs.alias(
                selected_story_arc_number=FilteredRelation(rel, condition=condition),
            )
            story_arc_number = self.order_agg_func("selected_story_arc_number__number")
        else:
            story_arc_number = NONE_INTEGERFIELD

        return qs.alias(story_arc_number=story_arc_number)

    def _annotate_page_count(self, qs, model):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        if model == Comic:
            return qs

        rel = self.rel_prefix + "page_count"
        page_count_sum = Sum(rel, distinct=True)
        if self.TARGET == "browser":
            qs = qs.alias(page_count=page_count_sum)
        else:
            qs = qs.annotate(page_count=page_count_sum)
        return qs

    def _annotate_bookmark_updated_at(self, qs, model):
        if not self.is_opds_1_acquisition and self.order_key != "bookmark_updated_at":
            return qs
        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(model)
        bm_updated_at_rel = f"{bm_rel}__updated_at"
        bmua_agg = self.order_agg_func(
            bm_updated_at_rel, default=NONE_DATETIMEFIELD, filter=bm_filter
        )
        return qs.annotate(bookmark_updated_at=bmua_agg)

    def _annotate_order_value(self, qs, model):
        """Annotate a main key for sorting and browser card display."""
        # Determine order func
        if self.TARGET == "metadata":
            return qs
        if model == Folder and self.order_key == "filename":
            order_value = F("name")
        elif model == Comic or self.order_key in _ANNOTATED_ORDER_FIELDS:
            # These are annotated in browser_annotaions
            order_value = F(self.order_key)
        else:
            agg_func = _ORDER_AGGREGATE_FUNCS[self.order_key]
            agg_func = self.order_agg_func if agg_func == Min else agg_func
            field = self.rel_prefix + self.order_key
            order_value = agg_func(field)

        if self.TARGET == "browser":
            qs = qs.annotate(order_value=order_value)
        else:
            qs = qs.alias(order_value=order_value)
        return qs

    def _annotate_search_scores(self, qs):
        """Annotate Search Scores."""
        if (
            self.TARGET not in frozenset({"browser", "cover"})
            or not self.fts_mode
            or self.params.get("order_by") != "search_score"  # type: ignore
        ):
            return qs
        return qs.annotate(search_score=ComicFTSRank())

    def annotate_order_aggregates(self, qs, model):
        """Annotate common aggregates between browser and metadata."""
        self.set_order_key()
        qs = qs.annotate(ids=JsonGroupArray("id", distinct=True))
        qs = self._annotate_search_scores(qs)
        qs = self._alias_sort_names(qs, model)
        qs = self._alias_filename(qs, model)
        qs = self._alias_story_arc_number(qs)
        qs = self._annotate_page_count(qs, model)
        qs = self._annotate_bookmark_updated_at(qs, model)
        if model != Comic:
            # comic orders on indexed fields when it can
            qs = self._annotate_order_value(qs, model)
        return qs

    def _annotate_group(self, qs, model):
        """Annotate Group."""
        value = "c" if model == Comic else self.model_group  # type: ignore
        return qs.annotate(group=Value(value, CharField(max_length=1)))

    @staticmethod
    def _get_bookmark_page_and_finished_counts(
        bm_filter, page_rel, finished_rel, page_count
    ):
        bookmark_page_case = Case(
            # When(**{bm_rel: None}, then=0),
            When(**{finished_rel: True}, then=page_count),
            default=page_rel,
            output_field=PositiveSmallIntegerField(),
        )

        bookmark_page = Sum(
            bookmark_page_case,
            default=0,
            filter=bm_filter,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )

        finished_count = Sum(
            finished_rel,
            default=0,
            filter=bm_filter,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )
        finished_aggregate = Q(child_count=finished_count)

        return bookmark_page, finished_aggregate

    def _annotate_group_bookmarks(self, bm_filter, page_rel, finished_rel):
        """Aggregate bookmark and finished states for groups."""
        page_count = f"{self.rel_prefix}page_count"
        return self._get_bookmark_page_and_finished_counts(
            bm_filter, page_rel, finished_rel, page_count
        )

    def _annotate_group_bookmarks_with_fts(self):
        """Aggregate bookmark and finished states for groups using subqueries to not break with the FTS match filter."""
        if not self.model:
            return 0, 0

        comic_qs = self.get_filtered_queryset(Comic)
        # Must group by the outer ref or it only does aggregates for one comic.
        group_rel = (
            "parent_folder"
            if self.model == Folder
            else "story_arc_numbers__story_arc"
            if self.model == StoryArc
            else self.model.__name__.lower()
        )
        group_rel_suffix = "name" if self.model == Volume else "sort_name"
        group_rel += "__" + group_rel_suffix
        comic_qs = comic_qs.filter(**{group_rel: OuterRef("pk")}).values(group_rel)

        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(Comic)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"
        page_count = "page_count"
        bookmark_page, finished_aggregate = self._get_bookmark_page_and_finished_counts(
            bm_filter, page_rel, finished_rel, page_count
        )

        comic_qs = comic_qs.annotate(page=bookmark_page, finished=finished_aggregate)
        bookmark_page = Subquery(comic_qs.values("page"))
        finished_aggregate = Subquery(comic_qs.values("finished"))

        return bookmark_page, finished_aggregate

    def _annotate_bookmarks(self, qs, model):
        """Hoist up bookmark annotations."""
        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(model)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if model == Comic:
            # Hoist comic bookmark and finished states
            bookmark_page = F(page_rel)
            finished_aggregate = F(finished_rel)
        elif self.fts_mode:
            # Aggregate bookmark and finished states for groups using subqueries to
            # not break with FTS match filter.
            bookmark_page, finished_aggregate = (
                self._annotate_group_bookmarks_with_fts()
            )
        else:
            # Aggregate bookmark and finished states for groups
            bookmark_page, finished_aggregate = self._annotate_group_bookmarks(
                bm_filter, page_rel, finished_rel
            )

        if (
            self.is_opds_1_acquisition
            or (self.is_model_comic and self.TARGET == "browser")
            or self.TARGET in frozenset({"metadata", "browser"})
        ):
            qs = qs.annotate(page=bookmark_page)

        if self.TARGET in frozenset({"metadata", "browser"}):
            qs = qs.annotate(finished=finished_aggregate)
        return qs

    def _annotate_progress(self, qs):
        """Compute progress for each member of a qs."""
        if self.TARGET not in frozenset({"metadata", "browser"}):
            return qs
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Page counts can be null with metadata turned off.
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        progress = Least(Coalesce(F("page"), 0) * 100.0 / F("page_count"), Value(100.0))
        return qs.annotate(progress=progress)

    def annotate_card_aggregates(self, qs, model):
        """Annotate aggregates that appear the browser card."""
        if model == Comic:
            # comic adds order_value for cards late
            qs = self._annotate_order_value(qs, model)
        qs = self._annotate_group(qs, model)
        qs = self.annotate_group_names(qs, model)
        qs = self._annotate_bookmarks(qs, model)
        qs = self._annotate_progress(qs)
        return qs.annotate(updated_ats=JsonGroupArray("updated_at", distinct=True))
