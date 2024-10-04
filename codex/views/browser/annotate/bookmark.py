"""Base view for metadata annotations."""

from django.db.models import (
    Case,
    F,
    Sum,
    Value,
    When,
)
from django.db.models.fields import BooleanField, PositiveSmallIntegerField
from django.db.models.functions import Least
from django.db.models.functions.comparison import Coalesce

from codex.logger.logging import get_logger
from codex.models import (
    Comic,
)
from codex.models.functions import JsonGroupArray
from codex.views.browser.annotate.order import BrowserAnnotateOrderView

LOG = get_logger(__name__)


class BrowserAnnotateBookmarkView(BrowserAnnotateOrderView):
    """Base class for views that need special metadata annotations."""

    def _get_group_bookmark_page_annotation(
        self, qs, bm_rel, bm_filter, page_rel, finished_rel
    ):
        """Get bookmark page subquery."""
        finished_filter = {finished_rel: True}
        prefix = "" if qs.model is Comic else self.rel_prefix
        page_count = prefix + "page_count"
        # Can't use a filtered relation for page & finished because of this
        # page_count case.
        bookmark_page_case = Case(
            When(**{bm_rel: None}, then=0),
            When(**finished_filter, then=page_count),
            default=page_rel,
            output_field=PositiveSmallIntegerField(),
        )
        return Sum(
            bookmark_page_case,
            default=0,
            filter=bm_filter,
            output_field=PositiveSmallIntegerField(),
            distinct=True,
        )

    @classmethod
    def _get_group_bookmark_finished_annotation(cls, qs, bm_filter, finished_rel):
        """Get finished_count subquery."""
        finished_count = Sum(
            finished_rel,
            default=0,
            filter=bm_filter,
            output_field=PositiveSmallIntegerField(),
            # distinct breaks this sum and only returns one. idk why.
        )
        qs = qs.alias(finished_count=finished_count)

        finished_aggregate = Case(
            When(finished_count=F("child_count"), then=True),
            When(finished_count=0, then=False),
            default=None,
            output_field=BooleanField(),
        )
        return qs, finished_aggregate

    def annotate_bookmarks(self, qs):
        """Hoist up bookmark annotations."""
        bm_rel = self._get_bm_rel(qs.model)
        bm_filter = self._get_my_bookmark_filter(bm_rel)
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if qs.model is Comic:
            bookmark_page = Sum(page_rel, filter=bm_filter, default=0)
            finished_aggregate = Sum(finished_rel, filter=bm_filter, default=False)
        else:
            bookmark_page = self._get_group_bookmark_page_annotation(
                qs, bm_rel, bm_filter, page_rel, finished_rel
            )
            qs, finished_aggregate = self._get_group_bookmark_finished_annotation(
                qs, bm_filter, finished_rel
            )

        if (
            (self.TARGET == "browser" and qs.model is Comic)
            or self.is_opds_acquisition
            or self.TARGET == "metadata"
        ):
            qs = qs.annotate(page=bookmark_page)
        else:
            qs = qs.alias(page=bookmark_page)

        qs = qs.annotate(finished=finished_aggregate)

        if not self.bmua_is_max:
            mbmua = self.get_max_bookmark_updated_at_aggregate(qs.model, JsonGroupArray)
            qs = qs.annotate(bookmark_updated_ats=mbmua)
        return qs

    def annotate_progress(self, qs):
        """Compute progress for each member of a qs."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Page counts can be null with metadata turned off.
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        progress = Least(Coalesce(F("page"), 0) * 100.0 / F("page_count"), Value(100.0))
        return qs.annotate(progress=progress)
