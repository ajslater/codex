"""Base view for metadata annotations."""

from os import sep
from types import MappingProxyType

from django.db.models import (
    F,
    FilteredRelation,
    Q,
    Value,
)
from django.db.models.aggregates import Avg, Count, Max, Min, Sum
from django.db.models.fields import CharField
from django.db.models.functions import Reverse, Right, StrIndex

from codex.models import (
    Comic,
    Folder,
    StoryArc,
)
from codex.models.functions import ComicFTSRank, JsonGroupArray
from codex.views.browser.order_by import (
    BrowserOrderByView,
)
from codex.views.const import (
    NONE_INTEGERFIELD,
    STORY_ARC_GROUP,
)
from codex.views.mixins import SharedAnnotationsMixin

_ORDER_AGGREGATE_FUNCS = MappingProxyType(
    # These are annotated to order_value because they're simple relations
    {
        "age_rating": Avg,
        "child_count": Min,
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
        "bookmark_updated_at",
        "child_count",
        "filename",
        "search_score",
        "sort_name",
        "story_arc_number",
    }
)


class BrowserAnnotateOrderView(BrowserOrderByView, SharedAnnotationsMixin):
    """Base class for views that need special metadata annotations."""

    CARD_TARGETS = frozenset({"browser", "metadata"})
    _OPDS_TARGETS = frozenset({"opds1", "opds2"})
    _PAGE_COUNT_TARGETS = frozenset(CARD_TARGETS | _OPDS_TARGETS)
    _COVER_AND_CARD_TARGETS = frozenset(CARD_TARGETS | {"cover"})

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._order_agg_func: type[Min | Max] | None = None
        self._is_opds_acquisition: bool | None = None
        self._opds_acquisition_groups: frozenset[str] | None = None
        self.bmua_is_max = False
        self._child_count_annotated = False

    @property
    def opds_acquisition_groups(self):
        """Memoize the opds acquisition groups."""
        if self._opds_acquisition_groups is None:
            groups = {"a", "f", "c"}
            groups |= {*self.valid_nav_groups[-2:]}
            self._opds_acquisition_groups = frozenset(groups)
        return self._opds_acquisition_groups

    @property
    def is_opds_acquisition(self):
        """Memoize if we're in an opds acquisition view."""
        if self._is_opds_acquisition is None:
            is_opds_acquisition = self.TARGET in self._OPDS_TARGETS
            if is_opds_acquisition:
                group = self.kwargs.get("group")
                is_opds_acquisition &= group in self.opds_acquisition_groups
                if is_opds_acquisition and group == "a":
                    pks = self.kwargs["pks"]
                    is_opds_acquisition &= bool(pks and 0 not in pks)
            self._is_opds_acquisition = is_opds_acquisition
        return self._is_opds_acquisition

    @property
    def order_agg_func(self):
        """Get the order aggregate function."""
        if self._order_agg_func is None:
            order_reverse = self.params.get("order_reverse")
            self._order_agg_func = Max if order_reverse else Min
        return self._order_agg_func

    def _alias_sort_names(self, qs):
        """Annotate sort_name."""
        if self.order_key != "sort_name" and not (
            qs.model is StoryArc and self.order_key == "story_arc_number"
        ):
            return qs
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        show = MappingProxyType(self.params["show"])
        sort_name_annotations = self.get_sort_name_annotations(
            qs.model, group, pks, show
        )
        if sort_name_annotations:
            qs = qs.alias(**sort_name_annotations)
            if qs.model is Comic:
                self._comic_sort_names = tuple(sort_name_annotations.keys())
        return qs

    def get_filename_func(self, model):
        """Get the filename creation function."""
        prefix = "" if model == Comic else self.rel_prefix
        path_rel = prefix + "path"

        return Right(
            path_rel,
            StrIndex(  # pyright: ignore[reportArgumentType],# ty: ignore[invalid-argument-type]
                Reverse(F(path_rel)),
                Value(sep),
            )
            - 1,
            output_field=CharField(),
        )

    def _alias_filename(self, qs):
        """Calculate filename from path in the db."""
        if self.order_key != "filename":
            return qs
        if qs.model is Folder:
            filename = F("name")
        else:
            filename_func = self.get_filename_func(qs.model)
            filename = self.order_agg_func(filename_func)
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
            story_arc_pks = self.params.get("filters", {}).get("story_arcs", ())

        # If we have one annotate it.
        if story_arc_pks:
            rel = self.get_rel_prefix(qs.model) + "story_arc_numbers"
            condition_rel = "pk" if qs.model is StoryArc else rel + "__story_arc"
            condition = Q(**{f"{condition_rel}__in": story_arc_pks})
            qs = qs.alias(
                selected_story_arc_number=FilteredRelation(rel, condition=condition),
            )
            story_arc_number = self.order_agg_func("selected_story_arc_number__number")
        else:
            story_arc_number = NONE_INTEGERFIELD

        return qs.alias(story_arc_number=story_arc_number)

    def _annotate_page_count(self, qs):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        if qs.model is Comic or (
            self.order_key != "page_count"
            and self.TARGET not in self._PAGE_COUNT_TARGETS
        ):
            return qs

        rel = self.rel_prefix + "page_count"
        page_count_sum = Sum(rel, distinct=True)
        if self.TARGET == "browser":
            qs = qs.alias(page_count=page_count_sum)
        else:
            qs = qs.annotate(page_count=page_count_sum)
        return qs

    def _annotate_bookmark_updated_at(self, qs):
        if self.is_opds_acquisition or self.order_key == "bookmark_updated_at":
            bmua_agg = self.get_max_bookmark_updated_at_aggregate(
                qs.model, agg_func=self.order_agg_func
            )
            # This is used by annotate.bookmark to avoid a
            # similar query.
            self.bmua_is_max = self.order_agg_func is Max
            qs = qs.annotate(bookmark_updated_at=bmua_agg)
        # This is used by the serializer to compute mtime
        return qs.annotate(bmua_is_max=Value(self.bmua_is_max))

    def _annotate_search_scores(self, qs):
        """Annotate Search Scores."""
        if (
            self.TARGET not in self._COVER_AND_CARD_TARGETS
            or self.order_key != "search_score"
        ):
            return qs

        # Rank is always the max of the relations, cannot aggregate?
        # group by here fixes duplicates with story_arc, probably because it's a long relation
        return qs.annotate(search_score=ComicFTSRank()).group_by("id")

    def annotate_child_count(self, qs):
        """Annotate child count."""
        if qs.model is Comic or self._child_count_annotated:
            return qs
        rel = self.rel_prefix + "pk"
        count_func = Count(rel, distinct=True)
        ann = {"child_count": count_func}
        qs = qs.alias(**ann) if self.TARGET == "opds2" else qs.annotate(**ann)
        self._child_count_annotated = True
        return qs

    def _annotate_order_child_count(self, qs):
        """Annotate child count for order."""
        if self.order_key != "child_count":
            return qs
        return self.annotate_child_count(qs)

    def annotate_order_value(self, qs):
        """Annotate a main key for sorting and browser card display."""
        # Determine order func
        if self.TARGET == "metadata":
            return qs
        if qs.model is Folder and self.order_key == "filename":
            order_value = F("name")
        elif qs.model is Comic:
            order_key = (
                "sort_name" if self.order_key == "child_count" else self.order_key
            )
            order_value = F(order_key)
        elif self.order_key in _ANNOTATED_ORDER_FIELDS:
            # These are annotated in browser_annotations
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

    def annotate_order_aggregates(self, qs):
        """Annotate common aggregates between browser and metadata."""
        qs = qs.annotate(ids=JsonGroupArray("id", distinct=True))
        qs = self._annotate_search_scores(qs)
        qs = self._alias_sort_names(qs)
        qs = self._alias_filename(qs)
        qs = self._alias_story_arc_number(qs)
        qs = self._annotate_page_count(qs)
        qs = self._annotate_bookmark_updated_at(qs)
        qs = self._annotate_order_child_count(qs)
        if qs.model is not Comic:
            # comic orders on indexed fields when it can
            qs = self.annotate_order_value(qs)
        return qs
