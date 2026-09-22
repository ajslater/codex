"""Base view for metadata annotations."""

from django.db.models import (
    Case,
    Count,
    F,
    Max,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.fields import BooleanField, PositiveSmallIntegerField
from django.db.models.functions import Least
from django.db.models.functions.comparison import Coalesce, Greatest

from codex.models import (
    Comic,
)
from codex.views.browser.annotate.order import BrowserAnnotateOrderView


class BrowserAnnotateBookmarkView(BrowserAnnotateOrderView):
    """Base class for views that need special metadata annotations."""

    def _get_collection_bookmark_page_annotation(
        self, qs, bm_rel, page_rel, finished_rel
    ) -> Sum:
        """Get the Σ of my read position over the collection's child comics."""
        prefix = "" if qs.model is Comic else self.rel_prefix
        page_count = prefix + "page_count"
        # A *finished* child contributes its whole page_count even when its
        # own bookmark page is partial (finished at page 3 of 24 still counts
        # 24), so this can't collapse to a plain Sum of ``bookmark__page``.
        # ``bm_rel`` is the my-bookmark filtered relation, so the join is at
        # most 1:1 per comic and the NULL arm covers comics I have never
        # opened -- no ``filter=`` and no ``distinct=`` needed. The old
        # ``distinct=True`` was ``SUM(DISTINCT ...)``, which sums the set of
        # distinct *values*: a dozen finished 24-page issues summed to 24,
        # so a single read child pinned the whole collection to 100%.
        bookmark_page_case = Case(
            When(**{bm_rel: None}, then=0),
            When(**{finished_rel: True}, then=page_count),
            default=page_rel,
            output_field=PositiveSmallIntegerField(),
        )
        return Sum(
            bookmark_page_case,
            default=0,
            output_field=PositiveSmallIntegerField(),
        )

    def _get_collection_bookmark_finished_annotation(self, qs, finished_rel) -> tuple:
        """Get the count of child comics I have finished, and the tri-state."""
        # ``COUNT(DISTINCT comic.id) FILTER (WHERE my_bm.finished)`` counts
        # each finished child exactly once however many joined rows it
        # produces, so it survives every fan-out the collection join can
        # create: an m2m field filter matching one comic on several tags, and
        # a comic sitting in two ``StoryArcNumber`` rows of the same arc
        # (``unique_together`` is ("story_arc", "number"), which permits it).
        # The old ``Sum(finished)`` counted joined rows, so an m2m filter
        # inverted the tri-state in both directions -- 6-of-12 read reported
        # fully read, 12-of-12 reported partial -- and one duplicated arc row
        # made an arc that could never report read. It is also the shape that
        # pairs with ``child_count``, which is the same COUNT DISTINCT.
        finished_count = Count(
            self.rel_prefix + "pk",
            distinct=True,
            filter=Q(**{finished_rel: True}),
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
        if qs.model is Comic:
            bm_rel = self.get_bm_rel(qs.model)
            bm_filter = self.get_my_bookmark_filter(bm_rel)
            # A comic has at most one bookmark of mine, so the filtered
            # aggregate is already 1:1 and needs no join rewrite.
            bookmark_page = Sum(f"{bm_rel}__page", filter=bm_filter, default=0)
            finished_aggregate = Sum(
                f"{bm_rel}__finished", filter=bm_filter, default=False
            )
        else:
            qs = self.alias_my_bookmark(qs)
            bm_rel = self.collection_bm_rel(qs.model)
            bookmark_page = self._get_collection_bookmark_page_annotation(
                qs, bm_rel, f"{bm_rel}__page", f"{bm_rel}__finished"
            )
            qs, finished_aggregate = self._get_collection_bookmark_finished_annotation(
                qs, f"{bm_rel}__finished"
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
            # The serializer folds this into the card mtime. A Max
            # aggregate replaces the old JSON_GROUP_ARRAY of every
            # bookmark timestamp per row plus a per-card Python
            # ISO-parse loop — the array was consumed solely to compute
            # a running max. Alias is distinct from
            # ``bookmark_updated_at``: when the primary sort is
            # bookmark_updated_at ascending that alias already holds a
            # Min aggregate, and the table-view collection branch
            # annotates it independently.
            mbmua = self.get_max_bookmark_updated_at_aggregate(
                qs.model, Max, bm_rel=self.collection_bm_rel(qs.model)
            )
            qs = qs.annotate(bookmark_updated_at_max=mbmua)
        return qs

    def annotate_progress(self, qs):
        """Compute progress for each member of a qs."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Page counts can be null with metadata turned off.
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        progress = Least(
            Coalesce(F("page"), 0)
            * 100.0
            / Greatest(Coalesce(F("page_count"), 1) - 1, 1),
            Value(100.0),
        )
        return qs.annotate(progress=progress)
