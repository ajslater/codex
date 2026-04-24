"""Cover pk annotation for browser card querysets."""

from django.db.models import OuterRef, Q, Subquery

from codex.models import Comic, Folder, Volume
from codex.models.paths import CustomCover
from codex.views.browser.annotate.card import _GROUP_BY, BrowserAnnotateCardView
from codex.views.const import CUSTOM_COVER_GROUP_RELATION, GROUP_RELATION


class BrowserAnnotateCoverView(BrowserAnnotateCardView):
    """
    Annotate cover_pk / cover_custom_pk on browser group cards.

    Pre-computes the representative comic pk per card via a correlated
    subquery, replacing the 72-request fan-out to ``CoverView`` with a
    single aggregation pass. Reproduces ``CoverView.get_group_filter``
    semantics exactly: direct group-fk match when ``dynamic_covers`` is
    on or the model is Volume/Folder; sort-name fuzzy match (correlated
    on the GROUP BY columns) otherwise.
    """

    def _cover_group_q(self, group_model) -> Q:
        """Group filter Q for a cover subquery, correlated via OuterRef."""
        group_rel = GROUP_RELATION[self.model_group]
        if self.params.get("dynamic_covers") or group_model in (Volume, Folder):
            return Q(**{f"{group_rel}__pk": OuterRef("pk")})

        # Fuzzy match: correlate on the GROUP BY columns. These are the
        # same columns used by add_group_by, so ``ids`` (the JsonGroupArray
        # of merged group pks) and the cover subquery pick the exact same
        # comic set — without recomputing sort_names in Python.
        group_by_cols = _GROUP_BY.get(group_model, ("sort_name",))
        correlation: dict = {
            f"{group_rel}__{col}": OuterRef(col) for col in group_by_cols
        }
        parent_route = self.params.get("parent_route", {})
        if parent_pks := parent_route.get("pks"):
            parent_rel = GROUP_RELATION[parent_route["group"]]
            correlation[f"{parent_rel}__pk__in"] = parent_pks
        return Q(**correlation)

    def _cover_filter_q(self, group_model) -> Q:
        """Build the full filter Q for the cover comic subquery."""
        q = self.get_acl_filter(Comic, self.request.user)
        q &= self._cover_group_q(group_model)
        q &= self.get_comic_field_filter(Comic)
        if self.is_bookmark_filtered:
            q &= self.get_bookmark_filter(Comic)
        include_q, exclude_q, fts_q = self.get_search_filters(Comic)
        return q & include_q & ~exclude_q & fts_q

    def _cover_comic_subquery(self, group_model) -> Subquery:
        """Correlated subquery returning one comic pk per outer group row."""
        q = self._cover_filter_q(group_model)
        qs = Comic.objects.filter(q).distinct()
        qs = self.annotate_order_aggregates(qs, for_cover=True)
        qs = self.add_order_by(qs)
        return Subquery(qs.values("pk")[:1])

    def _cover_custom_subquery(self, group_model) -> Subquery | None:
        """Correlated subquery returning a CustomCover pk, if applicable."""
        if group_model is Volume or not self.params.get("custom_covers"):
            return None
        group = self.kwargs.get("group")
        group_rel = CUSTOM_COVER_GROUP_RELATION.get(group)
        if not group_rel:
            return None
        qs = CustomCover.objects.filter(**{group_rel: OuterRef("pk")}).values("pk")[:1]
        return Subquery(qs)

    def annotate_cover(self, qs):
        """Annotate cover_pk (and optionally cover_custom_pk) on group cards."""
        if qs.model is Comic:
            # Comic cards use their own pk as the cover pk — the serializer
            # falls back to pk when cover_pk is absent.
            return qs
        if self.params.get("search"):
            # FTS MATCH inside a correlated subquery re-scans the FTS index
            # per outer row, adding ~900ms on a ~100-group browse. Let the
            # frontend fall back to the legacy group+pks cover URL; each
            # cover request still benefits from the Option-A pipeline trim.
            return qs
        qs = qs.annotate(cover_pk=self._cover_comic_subquery(qs.model))
        custom_sq = self._cover_custom_subquery(qs.model)
        if custom_sq is not None:
            qs = qs.annotate(cover_custom_pk=custom_sq)
        return qs
