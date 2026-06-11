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
            # Also apply fts_q directly — but only when the cover subquery's
            # ORDER BY actually references the rank. The direct fts_q forces
            # a JOIN to ``codex_comicfts`` with MATCH active, populating
            # ``codex_comicfts.rank`` so ``search_score=ComicFTSRank()`` is
            # resolvable in the subquery's ORDER BY; without it the cover
            # picked would be arbitrary among the FTS matches rather than
            # the highest-ranked one. For every other order key the rank is
            # unused and the MATCH re-executes once per correlated cover
            # evaluation (a name-sorted search browse measured 135s vs 14s
            # with the pre-materialized ``fts_sq`` membership test alone).
            if self.order_key == "search_score":
                q &= fts_q
        return q

    def _cover_comic_ordered_qs(self, collection_model):
        """Ordered comic queryset feeding the cover pk + mtime subqueries."""
        q = self._cover_filter_q(collection_model)
        qs = Comic.objects.filter(q).distinct()
        qs = self.annotate_order_aggregates(qs, for_cover=True)
        return self.add_order_by(qs, for_cover=True)

    def _cover_custom_subqueries(self):
        """Return (pk, updated_at) subqueries for a CustomCover, or (None, None)."""
        if not self.params.get("custom_covers"):
            return None, None
        # ``model_collection`` is the collection the cards being annotated belong to
        # (the *child* of the URL collection). ``kwargs["collection"]`` is the URL
        # collection itself, which is one level too high for the cover lookup —
        # e.g. on ``/r/0/1`` the URL collection is ``r`` but the cards are
        # publishers, so the relation we need is ``publisher``, not the
        # (nonexistent) ``r`` entry.
        collection_rel = CUSTOM_COVER_COLLECTION_RELATION.get(self.model_collection)
        if not collection_rel:
            return None, None
        base = CustomCover.objects.filter(**{collection_rel: OuterRef("pk")})
        return (
            Subquery(base.values("pk")[:1]),
            Subquery(base.values("updated_at")[:1]),
        )

    def annotate_cover(self, qs):
        """Annotate cover_pk / cover_custom_pk / cover_custom_mtime on collection card."""
        if qs.model is Comic:
            # Comic cards use their own pk + updated_at; the serializer falls
            # back to those when the cover_* annotations are absent.
            return qs
        cover_qs = self._cover_comic_ordered_qs(qs.model)
        # The representative comic's own updated_at (the cover ``?ts=``
        # source) is NOT annotated here: a ``.values("updated_at")``
        # subquery would be a second execution of the identical correlated
        # cover query per card (measured 40-49% of the card query).
        # ``attach_cover_mtimes`` resolves it post-pagination with one
        # batched pk lookup over the page's cover_pks.
        qs = qs.annotate(cover_pk=Subquery(cover_qs.values("pk")[:1]))
        custom_pk_sq, custom_mtime_sq = self._cover_custom_subqueries()
        if custom_pk_sq is not None:
            # Cheap rowid lookups; a custom cover overrides the comic
            # cover, so its mtime wins in ``attach_cover_mtimes``.
            qs = qs.annotate(
                cover_custom_pk=custom_pk_sq, cover_custom_mtime=custom_mtime_sq
            )
        return qs

    @staticmethod
    def attach_cover_mtimes(collection_qs):
        """
        Attach ``cover_mtime`` to the page's collection rows in one batch.

        Materializes the (paginated) queryset — priming the result cache
        the serializer reuses — and resolves every representative comic's
        ``updated_at`` with a single indexed ``pk__in`` query, instead of
        re-running the correlated cover subquery per card. The cover
        ``?ts=`` still only changes when the shown image does.
        """
        collections = list(collection_qs)
        cover_pks = {pk for c in collections if (pk := getattr(c, "cover_pk", None))}
        mtimes = (
            dict(Comic.objects.filter(pk__in=cover_pks).values_list("pk", "updated_at"))
            if cover_pks
            else {}
        )
        for c in collections:
            custom_mtime = getattr(c, "cover_custom_mtime", None)
            c.cover_mtime = custom_mtime or mtimes.get(getattr(c, "cover_pk", None))
        return collection_qs
