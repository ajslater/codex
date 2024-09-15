"""Base view for metadata annotations."""

from types import MappingProxyType

from django.db.models import (
    Case,
    F,
    OuterRef,
    Sum,
    Value,
    When,
)
from django.db.models.expressions import Subquery
from django.db.models.fields import BooleanField, CharField, PositiveSmallIntegerField
from django.db.models.functions import Least
from django.db.models.functions.comparison import Coalesce

from codex.logger.logging import get_logger
from codex.models import (
    BrowserGroupModel,
    Comic,
    Folder,
    StoryArc,
)
from codex.models.functions import JsonGroupArray
from codex.views.browser.annotate.order import BrowserAnnotateOrderView

LOG = get_logger(__name__)

_BOOKMARK_GROUP_REL = MappingProxyType(
    {Folder: "parent_folder", StoryArc: "story_arc_numbers__story_arc"}
)


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

    def _get_bookmark_comic_qs(self, qs):
        """Get the comic qs for  subquery."""
        comic_qs = self.get_filtered_queryset(Comic)
        group_by = _BOOKMARK_GROUP_REL.get(qs.model, qs.model.__name__.lower())
        group_rel = group_by + "__pk"
        group_filter = {group_rel: OuterRef("pk")}
        comic_qs = comic_qs.filter(**group_filter)
        # Must group by the outer ref or it only does aggregates for one comic?
        return comic_qs.values(group_rel)

    @staticmethod
    def _get_bookmark_page_subquery(comic_qs, finished_rel, bm_rel, bm_filter):
        """Get bookmark page subquery."""
        finished_filter = {finished_rel: True}
        page_count = "page_count"
        page_rel = f"{bm_rel}__page"
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
        return Subquery(comic_qs.annotate(page=bookmark_page).values("page"))

    @staticmethod
    def _get_finished_count_subquery(comic_qs, finished_rel, bm_filter):
        """Get finished_count subquery."""
        finished_count = Sum(
            finished_rel,
            default=0,
            filter=bm_filter,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )
        return Subquery(
            comic_qs.annotate(finished_count=finished_count).values("finished_count")
        )

    def _get_bookmark_page_and_finished_subqueries(self, qs):
        comic_qs = self._get_bookmark_comic_qs(qs)
        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(Comic)
        finished_rel = f"{bm_rel}__finished"
        bookmark_page = self._get_bookmark_page_subquery(comic_qs, finished_rel, bm_rel, bm_filter)
        finished_count = self._get_finished_count_subquery(comic_qs, finished_rel, bm_filter)
        return bookmark_page, finished_count

    def _annotate_group_bookmarks(self, qs):
        """Aggregate bookmark and finished states for groups using subqueries to not break the FTS match filter."""
        # Using subqueries is also faster for non-fts queries.
        # XXX These are slow for large groups.
        bookmark_page, finished_count = self._get_bookmark_page_and_finished_subqueries(
            qs
        )
        qs = qs.alias(finished_count=finished_count)

        finished_aggregate = Case(
            When(finished_count=F("child_count"), then=True),
            When(finished_count=0, then=False),
            default=None,
            output_field=BooleanField(),
        )

        return qs, bookmark_page, finished_aggregate

    def _annotate_comic_bookmarks(self, qs):
        """Hoist comic bookmark and finished states."""
        bm_rel, _ = self.get_bookmark_rel_and_filter(qs.model)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        bookmark_page = Coalesce(page_rel, 0)
        finished_aggregate = Coalesce(finished_rel, False)
        return bookmark_page, finished_aggregate

    def _annotate_bookmarks(self, qs):
        """Hoist up bookmark annotations."""
        if qs.model is Comic:
            page, finished = self._annotate_comic_bookmarks(qs)
        else:
            qs, page, finished = self._annotate_group_bookmarks(qs)
            page = Value(0)
            # finished = Value(False)


        if (
            self.is_opds_1_acquisition
            or self.is_model_comic
            and self.TARGET == "browser"
        ):
            qs = qs.annotate(page=page)
        elif self.TARGET in frozenset({"metadata", "browser"}):
            qs = qs.alias(page=page)

        if self.TARGET in frozenset({"metadata", "browser"}):
            qs = qs.annotate(finished=finished)

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
