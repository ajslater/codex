"""Base view for metadata annotations."""

from django.db.models import (
    Case,
    F,
    OuterRef,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.expressions import Subquery
from django.db.models.fields import CharField, PositiveSmallIntegerField
from django.db.models.functions import Least
from django.db.models.functions.comparison import Coalesce

from codex.logger.logging import get_logger
from codex.models import (
    BrowserGroupModel,
    Comic,
    Folder,
    StoryArc,
    Volume,
)
from codex.models.functions import JsonGroupArray
from codex.views.browser.annotate_order import BrowserAnnotateOrderView

LOG = get_logger(__name__)


class BrowserAnnotateCardView(BrowserAnnotateOrderView):
    """Base class for views that need special metadata annotations."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.is_opds_1_acquisition = False
        self.comic_sort_names = ()
        self.bm_annotataion_data: dict[BrowserGroupModel, tuple[str, dict]] = {}

    def _annotate_group(self, qs):
        """Annotate Group."""
        value = "c" if qs.model is Comic else self.model_group  # type: ignore
        return qs.annotate(group=Value(value, CharField(max_length=1)))

    def _get_bookmark_page_and_finished_counts(self):
        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(Comic)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"
        page_count = "page_count"

        finished_filter = {finished_rel: True}
        bookmark_page_case = Case(
            When(**{bm_rel: None}, then=0),
            When(**finished_filter, then=page_count),
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

    def _annotate_group_bookmarks(self):
        """Aggregate bookmark and finished states for groups using subqueries to not break with the FTS match filter."""
        # Using these subqueries is faster even though it's not neccissary for non-fts queries.
        if not self.model:
            return 0, 0

        comic_qs = self.get_filtered_queryset(Comic)
        # Must group by the outer ref or it only does aggregates for one comic.
        group_rel = (
            "parent_folder"
            if self.model is Folder
            else "story_arc_numbers__story_arc"
            if self.model is StoryArc
            else self.model.__name__.lower()
        )
        group_rel_suffix = "name" if self.model is Volume else "sort_name"
        group_rel += "__" + group_rel_suffix
        comic_qs = comic_qs.filter(**{group_rel: OuterRef("pk")}).values(group_rel)
        bookmark_page, finished_aggregate = (
            self._get_bookmark_page_and_finished_counts()
        )

        comic_qs = comic_qs.annotate(page=bookmark_page, finished=finished_aggregate)
        bookmark_page = Subquery(comic_qs.values("page"))
        finished_aggregate = Subquery(comic_qs.values("finished"))

        return bookmark_page, finished_aggregate

    def _annotate_bookmarks(self, qs):
        """Hoist up bookmark annotations."""
        # XXX These are slow for large groups.
        bm_rel, _bm_filter = self.get_bookmark_rel_and_filter(qs.model)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if qs.model is Comic:
            # Hoist comic bookmark and finished states
            bookmark_page = Coalesce(page_rel, 0)
            finished_aggregate = Coalesce(finished_rel, False)
        else:
            # FTS mode is faster?
            # Aggregate bookmark and finished states for groups using subqueries to
            # not break with FTS match filter.
            bookmark_page, finished_aggregate = self._annotate_group_bookmarks()

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

    def annotate_card_aggregates(self, qs):
        """Annotate aggregates that appear the browser card."""
        if qs.model is Comic:
            # comic adds order_value for cards late
            qs = self._annotate_order_value(qs)
        qs = self._annotate_group(qs)
        qs = self.annotate_group_names(qs)
        qs = self._annotate_bookmarks(qs)
        qs = self._annotate_progress(qs)
        return qs.annotate(updated_ats=JsonGroupArray("updated_at", distinct=True))
