"""Cover pk annotation for browser card querysets."""

from django.db.models import OuterRef, Q, Subquery

from codex.models import Comic, Folder, Volume
from codex.models.paths import CustomCover
from codex.views.browser.annotate.card import _COLLECTION_BY, BrowserAnnotateCardView
from codex.views.const import COLLECTION_RELATION, CUSTOM_COVER_COLLECTION_RELATION


class BrowserAnnotateCoverView(BrowserAnnotateCardView):
    """
    Annotate cover_pk / cover_custom_pk on browser collection cards.

    Pre-computes the representative comic pk per card via a correlated
    subquery, replacing the 72-request fan-out to ``CoverView`` with a
    single aggregation pass. Reproduces ``CoverView.get_collection_filter``
    semantics exactly: direct collection-fk match when ``dynamic_covers`` is
    on or the model is Volume/Folder; sort-name fuzzy match (correlated
    on the GROUP BY columns) otherwise.
    """

    def _cover_collection_q(self, collection_model) -> Q:
        """Build the collection filter Q for a cover subquery (correlated via OuterRef)."""
        collection_rel = COLLECTION_RELATION[self.model_collection]
        if self.params.get("dynamic_covers") or collection_model in (Volume, Folder):
            # Folders are hierarchical: parent_folder is the direct FK, but the
            # browse filter uses the ``folders`` M2M that includes every
            # ancestor folder. A Folder card's cover must be pickable from any
            # comic in a descendant subfolder, not just direct children —
            # otherwise parent folders that contain only subfolders fall back
            # to the card's own pk and serve the missing-cover placeholder.
            if collection_model is Folder:
                return Q(folders__pk=OuterRef("pk"))
            return Q(**{f"{collection_rel}__pk": OuterRef("pk")})

        # Fuzzy match: correlate on the GROUP BY columns. These are the
        # same columns used by add_group_by, so ``ids`` (the JsonGroupArray
        # of merged collection pks) and the cover subquery pick the exact same
        # comic set — without recomputing sort_names in Python.
        collection_by_cols = _COLLECTION_BY.get(collection_model, ("sort_name",))
        correlation: dict = {
            f"{collection_rel}__{col}": OuterRef(col) for col in collection_by_cols
        }
        parent_route = self.params.get("parent_route", {})
        if parent_pks := parent_route.get("pks"):
            parent_rel = COLLECTION_RELATION[parent_route["collection"]]
            correlation[f"{parent_rel}__pk__in"] = parent_pks
        return Q(**correlation)

    def _cover_filter_q(self, collection_model) -> Q:
        """Build the full filter Q for the cover comic subquery."""
        q = self.get_acl_filter(Comic, self.request.user)
        q &= self._cover_collection_q(collection_model)
        q &= self.get_comic_field_filter(Comic)
        if self.is_bookmark_filtered:
            q &= self.get_bookmark_filter(Comic)
        # Apply favorites-only the same way ``_get_query_filters`` does for
        # the outer browser query. Without this the topmost collection's cover
        # subquery happily picks a non-favorited descendant, while
        # intermediate collections (whose query already runs through the main
        # filter pipeline) honor it.
        q &= self.get_favorite_filter(Comic)
        include_q, exclude_q, fts_q = self.get_search_filters(Comic)
        q &= include_q & ~exclude_q
        if fts_q:
            # pk__in over the pre-materialized FTS match set: SQLite
            # materializes this sub-SELECT once, giving the correlated cover
            # subquery a cheap indexed membership test instead of re-scanning
            # the FTS5 virtual table per outer collection row for the filter.
            fts_sq = Comic.objects.filter(fts_q).values("pk")
            q &= Q(pk__in=fts_sq)
            # Also apply fts_q directly: this forces a JOIN to
            # ``codex_comicfts`` with MATCH active, populating
            # ``codex_comicfts.rank`` so ``search_score=ComicFTSRank()`` is
            # resolvable in the cover subquery's ORDER BY. Without this, the
            # cover picked for a collection would be arbitrary among the FTS
            # matches rather than the highest-ranked one. The MATCH is
            # constant across outer rows, so SQLite's planner typically
            # hoists / shares it with the pre-materialized ``fts_sq``.
            q &= fts_q
        return q

    def _cover_comic_subquery(self, collection_model) -> Subquery:
        """Correlated subquery returning one comic pk per outer collection row."""
        q = self._cover_filter_q(collection_model)
        qs = Comic.objects.filter(q).distinct()
        qs = self.annotate_order_aggregates(qs, for_cover=True)
        qs = self.add_order_by(qs, for_cover=True)
        return Subquery(qs.values("pk")[:1])

    def _cover_custom_subquery(self) -> Subquery | None:
        """Correlated subquery returning a CustomCover pk, if applicable."""
        if not self.params.get("custom_covers"):
            return None
        # ``model_collection`` is the collection the cards being annotated belong to
        # (the *child* of the URL collection). ``kwargs["collection"]`` is the URL
        # collection itself, which is one level too high for the cover lookup —
        # e.g. on ``/r/0/1`` the URL collection is ``r`` but the cards are
        # publishers, so the relation we need is ``publisher``, not the
        # (nonexistent) ``r`` entry.
        collection_rel = CUSTOM_COVER_COLLECTION_RELATION.get(self.model_collection)
        if not collection_rel:
            return None
        qs = CustomCover.objects.filter(**{collection_rel: OuterRef("pk")}).values("pk")[:1]
        return Subquery(qs)

    def annotate_cover(self, qs):
        """Annotate cover_pk (and optionally cover_custom_pk) on collection card."""
        if qs.model is Comic:
            # Comic cards use their own pk as the cover pk — the serializer
            # falls back to pk when cover_pk is absent.
            return qs
        qs = qs.annotate(cover_pk=self._cover_comic_subquery(qs.model))
        custom_sq = self._cover_custom_subquery()
        if custom_sq is not None:
            qs = qs.annotate(cover_custom_pk=custom_sq)
        return qs
