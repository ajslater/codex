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
from django.db.models.fields import BooleanField, PositiveSmallIntegerField
from django.db.models.functions import Least
from django.db.models.functions.comparison import Coalesce
from django.db.models.query_utils import FilteredRelation

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


class BrowserAnnotateBookmarkView(BrowserAnnotateOrderView):
    """Base class for views that need special metadata annotations."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.bm_annotataion_data: dict[BrowserGroupModel, tuple[str, dict]] = {}

    @staticmethod
    def _add_bookmark_outer_ref_filter(comic_qs, model):
        group_by = _BOOKMARK_GROUP_REL.get(model, model.__name__.lower())
        # Values group_by here makes the aggregate work.
        comic_qs = comic_qs.values(group_by)
        group_filter = {group_by: OuterRef("pk")}
        return comic_qs.filter(**group_filter)

    @classmethod
    def _get_bookmark_page_subquery(cls, comic_qs, finished_rel, bm_rel):
        """Get bookmark page subquery."""
        finished_filter = {finished_rel: True}
        page_rel = f"{bm_rel}__page"
        bookmark_page_case = Case(
            When(**{bm_rel: None}, then=0),
            When(**finished_filter, then="page_count"),
            default=page_rel,
            output_field=PositiveSmallIntegerField(),
        )
        bookmark_page = Sum(
            bookmark_page_case,
            default=0,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )
        comic_qs = comic_qs.annotate(bookmark_page=bookmark_page).values(
            "bookmark_page"
        )
        return Subquery(comic_qs)

    @classmethod
    def _get_finished_count_subquery(cls, comic_qs, finished_rel):
        """Get finished_count subquery."""
        finished_count = Sum(
            finished_rel,
            default=0,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )

        comic_qs = comic_qs.annotate(finished_count=finished_count).values(
            "finished_count"
        )
        return Subquery(comic_qs)

    def _get_bookmark_page_and_finished_subqueries(self, model):
        """Get bookmark page and finished_count subqueries."""
        # Use outerref as the group_filter .
        comic_qs = self.get_filtered_queryset(Comic, group_filter=False, acl_filter=False)
        comic_qs = self._add_bookmark_outer_ref_filter(comic_qs, model)
        bm_rel = self._get_bm_rel(Comic)
        bm_filter = self._get_my_bookmark_filter(bm_rel)
        comic_qs = comic_qs.annotate(
            my_bookmark=FilteredRelation("bookmark", condition=bm_filter)
        )
        my_bm_rel = "my_bookmark"
        finished_rel = f"{my_bm_rel}__finished"
        bookmark_page = self._get_bookmark_page_subquery(
            comic_qs, finished_rel, my_bm_rel
        )
        finished_count = self._get_finished_count_subquery(comic_qs, finished_rel)
        return bookmark_page, finished_count

    def _annotate_group_bookmarks(self, model):
        """Aggregate bookmark and finished states for groups using subqueries to not break the FTS match filter."""
        # Using subqueries is also faster for non-fts queries.
        # XXX These are slow for large groups.
        bookmark_page, finished_count = self._get_bookmark_page_and_finished_subqueries(
            model
        )

        finished_aggregate = Case(
            When(finished_count=F("child_count"), then=True),
            When(finished_count=0, then=False),
            default=None,
            output_field=BooleanField(),
        )

        return bookmark_page, finished_count, finished_aggregate

    def _annotate_comic_bookmarks(self, model):
        """Hoist comic bookmark and finished states."""
        bm_rel = self._get_bm_rel(model)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        bookmark_page = Coalesce(page_rel, 0)
        finished_aggregate = Coalesce(finished_rel, False)
        return bookmark_page, None, finished_aggregate

    def annotate_bookmarks(self, qs):
        """Hoist up bookmark annotations."""
        if qs.model is Comic:
            page, finished_count, finished = self._annotate_comic_bookmarks(qs.model)
        else:
            page, finished_count, finished = self._annotate_group_bookmarks(qs.model)

        if (
            (self.TARGET == "browser" and qs.model is Comic)
            or self.is_opds_1_acquisition
            or self.TARGET == "metadata"
        ):
            qs = qs.annotate(page=page)
        else:
            qs = qs.alias(page=page)

        if finished_count:
            # Part of the finished calculation
            qs = qs.alias(finished_count=finished_count)
        qs = qs.annotate(finished=finished)

        mbmua = self.get_max_bookmark_updated_at_aggregate(qs.model, JsonGroupArray)
        return qs.annotate(bookmark_updated_ats=mbmua)


    def annotate_progress(self, qs):
        """Compute progress for each member of a qs."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Page counts can be null with metadata turned off.
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        progress = Least(Coalesce(F("page"), 0) * 100.0 / F("page_count"), Value(100.0))
        qs = qs.annotate(progress=progress)
        print(qs.query)
        return qs
