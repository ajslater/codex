"""Browser breadcrumbs calculations."""

from pathlib import PurePath
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from django.db.models import QuerySet

from codex.collection import Collection
from codex.models import (
    BrowserCollectionModel,
    Comic,
    Imprint,
    Series,
    Volume,
)
from codex.models.collections import Folder as FolderModel
from codex.models.collections import Publisher
from codex.views.browser.paginate import BrowserPaginateView
from codex.views.const import (
    COLLECTION_MODEL_MAP,
    FOLDER_COLLECTION,
    STORY_ARC_COLLECTION,
)
from codex.views.util import Route

if TYPE_CHECKING:
    from codex.models.collections import Folder

_COLLECTION_INSTANCE_SELECT_RELATED: MappingProxyType[
    type[BrowserCollectionModel], tuple[str, ...]
] = MappingProxyType(
    {
        Comic: ("series", "volume"),
        Volume: ("series", "imprint", "publisher"),
        Series: ("imprint", "publisher"),
        Imprint: ("publisher",),
    }
)

# Map from collection to the FK attribute chain for walking up the hierarchy.
# Each entry is (parent_collection, attribute_on_instance). Keyed by ``Collection``
# members so the lookup resolves against the collection-valued ``kwargs["collection"]``.
_COLLECTION_PARENT_CHAIN: MappingProxyType[
    Collection, tuple[tuple[Collection, str], ...]
] = MappingProxyType(
    {
        Collection.VOLUME: (
            (Collection.SERIES, "series"),
            (Collection.IMPRINT, "imprint"),
            (Collection.PUBLISHER, "publisher"),
        ),
        Collection.SERIES: (
            (Collection.IMPRINT, "imprint"),
            (Collection.PUBLISHER, "publisher"),
        ),
        Collection.IMPRINT: ((Collection.PUBLISHER, "publisher"),),
        Collection.PUBLISHER: (),
    }
)


class BrowserBreadcrumbsView(BrowserPaginateView):
    """Browser breadcrumbs calculations."""

    def __init__(self, *args, **kwargs) -> None:
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        # Use 0 to indicate unmemoized because None is a valid value
        self._collection_instance: BrowserCollectionModel | None | int = 0

    def _get_collection_query(self, model):
        """Get the collection query for the collection instance."""
        pks = self.kwargs.get("pks")
        qs = model.objects.filter(pk__in=pks)
        if select_related := _COLLECTION_INSTANCE_SELECT_RELATED.get(model):
            qs = qs.select_related(*select_related)
        order_by = "name" if model is Volume else "sort_name"
        return qs.order_by(order_by)

    def _handle_collection_query_missing_model(self, model) -> QuerySet:
        """Handle a missing model for the collection instance."""
        collection = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page")
        if not (collection == Collection.ROOT and not pks and page == 1):
            reason = f"{collection}__in={pks} does not exist!"
            # ``raise_redirect`` is ``NoReturn``; the type checker
            # follows the early-return shape so the caller below
            # is the only path that produces a queryset.
            self.raise_redirect(reason, route_mask={"collection": collection})
        return model.objects.none()

    @property
    def collection_instance(self) -> BrowserCollectionModel | None:
        """Memoize collection instance for getting collection names & counts."""
        if self._collection_instance == 0:
            collection = self.kwargs.get("collection")
            model = COLLECTION_MODEL_MAP[collection]
            pks = self.kwargs.get("pks")
            if model and pks and 0 not in pks:
                try:
                    collection_query = self._get_collection_query(model)
                except model.DoesNotExist:
                    collection_query = self._handle_collection_query_missing_model(
                        model
                    )
            else:
                if not model:
                    model = Publisher
                collection_query = model.objects.none()
            self._collection_instance = collection_query.first()
        # ``_collection_instance`` carries an ``int`` sentinel (``0``) for the
        # unmemoized state; by this point it's been resolved to a real
        # model row or ``None``.
        return cast("BrowserCollectionModel | None", self._collection_instance)

    def _build_collection_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for browse collection mode by walking FK parents."""
        gi = self.collection_instance
        collection = self.kwargs["collection"]
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]

        if not gi:
            return (Route(Collection.ROOT, (), 1, ""),)

        # Start with current crumb
        crumbs: list[Route] = [Route(collection, pks, page, gi.name)]

        # Walk up the parent chain via FKs
        vng = self.valid_nav_collections
        parent_chain = _COLLECTION_PARENT_CHAIN.get(collection, ())
        for parent_collection, attr in parent_chain:
            if parent_collection not in vng:
                continue
            if parent := getattr(gi, attr, None):
                crumbs.append(Route(parent_collection, (parent.pk,), 1, parent.name))
            else:
                crumbs.append(Route(parent_collection, (), 1, ""))

        # Always add root
        crumbs.append(Route(Collection.ROOT, (), 1, ""))
        crumbs.reverse()
        return tuple(crumbs)

    def _build_folder_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for folder mode by walking parent_folder FKs."""
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        # In folder mode ``collection_instance`` is a Folder (or None) by
        # construction — the caller branches on ``collection == FOLDER_COLLECTION``.
        folder = cast("Folder | None", self.collection_instance)
        name = folder.name if folder and pks else ""

        crumbs: list[Route] = [Route(FOLDER_COLLECTION, pks, page, name)]

        if folder:
            # Batch the ancestor chain in one query via the indexed
            # materialized ``path`` instead of lazy ``parent_folder``
            # walking — that issued one SELECT per ancestor level (a
            # depth-12 folder paid 11 round-trips per browse with cold
            # cachalot, and every import invalidates the Folder table).
            # ``PurePath.parents`` yields nearest-first; prefixes above
            # the library root match no rows and drop out, and
            # ``library_id`` keeps sibling libraries' folders excluded.
            prefixes = [str(p) for p in PurePath(folder.path).parents]
            ancestors = {
                ancestor.path: ancestor
                for ancestor in FolderModel.objects.filter(
                    library_id=folder.library_id,  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
                    path__in=prefixes,
                ).only("pk", "path", "name")
            }
            crumbs.extend(
                Route(FOLDER_COLLECTION, (ancestor.pk,), 1, ancestor.name)
                for prefix in prefixes
                if (ancestor := ancestors.get(prefix))
            )

        # Add folder root if not already there
        if crumbs[-1].pks:
            crumbs.append(Route(FOLDER_COLLECTION, (), 1, ""))

        crumbs.reverse()
        return tuple(crumbs)

    def _build_story_arc_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for story arc mode."""
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        gi = self.collection_instance
        name = gi.name if gi else ""

        crumbs: list[Route] = [Route(STORY_ARC_COLLECTION, pks, page, name)]

        # Add story arc root if viewing a specific arc
        if pks and 0 not in pks:
            crumbs.insert(0, Route(STORY_ARC_COLLECTION, (), 1, ""))

        return tuple(crumbs)

    def get_breadcrumbs(self) -> tuple[Route, ...]:
        """Compute breadcrumbs by browser mode from FK hierarchy."""
        collection = self.kwargs["collection"]
        if collection == FOLDER_COLLECTION:
            return self._build_folder_breadcrumbs()
        if collection == STORY_ARC_COLLECTION:
            return self._build_story_arc_breadcrumbs()
        return self._build_collection_breadcrumbs()
