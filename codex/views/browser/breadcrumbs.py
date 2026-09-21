"""Browser breadcrumbs calculations."""

from pathlib import PurePath
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, cast

from codex.collection import Collection
from codex.models import (
    BrowserCollectionModel,
    Comic,
    Imprint,
    Series,
    Volume,
)
from codex.models.collections import Folder as FolderModel
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
        self._collection_instance: BrowserCollectionModel | int | None = 0

    def _get_collection_query(self, model):
        """
        Get the collection query for the collection instance.

        ``comics`` is a valid collection segment, so ``model`` here can
        be Comic and the name this resolves is then the comic's own
        title. It also feeds ``BrowserTitleView._get_collection_name``,
        reached from the browser and both OPDS versions.

        A row this user may not see -- a hidden library, an age rating
        above theirs, or a scanner-stamped pending delete -- is simply
        absent from this queryset, exactly like a pk that never
        existed. ``collection_instance`` turns that emptiness into a
        redirect.
        """
        pks = self.kwargs.get("pks")
        # The full ACL, not just the pending-delete half: the pks come
        # straight off the route, so a hand-typed url would otherwise
        # name a collection out of a library the user cannot see or one
        # above their age rating. ``distinct()`` because every non-Comic
        # model reaches ``library_id`` and the rating index through the
        # multi-valued ``comic__`` hop.
        qs = model.objects.filter(
            self.get_acl_filter(model, self.request.user), pk__in=pks
        ).distinct()
        if select_related := _COLLECTION_INSTANCE_SELECT_RELATED.get(model):
            qs = qs.select_related(*select_related)
        order_by = "name" if model is Volume else "sort_name"
        return qs.order_by(order_by)

    def _raise_unresolved_collection_redirect(self) -> NoReturn:
        """Send the client up a level when the route names nothing it may see."""
        collection = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        # Counts and collection values only -- never a name, since the
        # whole point is that this user may not have the name.
        reason = f"{collection}__in={pks} does not resolve"
        self.raise_redirect(reason, route_mask={"collection": collection})

    @property
    def collection_instance(self) -> BrowserCollectionModel | None:
        """
        Memoize collection instance for getting collection names & counts.

        ``None`` means "no collection was asked for" -- the root listing
        of a collection, which has no pks. A route that *does* name pks
        and resolves nothing raises a 303 up to that collection's root
        instead of rendering a page with a nameless crumb and an empty
        body. The redirect carries the route in its body with no
        ``Location`` header, the same shape ``BrowserValidateView``
        already uses.
        """
        if self._collection_instance == 0:
            collection = self.kwargs.get("collection")
            model = COLLECTION_MODEL_MAP[collection]
            pks = self.kwargs.get("pks")
            instance = None
            if model and pks and 0 not in pks:
                instance = self._get_collection_query(model).first()
                if instance is None:
                    self._raise_unresolved_collection_redirect()
            self._collection_instance = instance
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
        # It is only ``None`` at the folder root, where ``pks`` is empty:
        # an unresolvable folder pk redirects instead.
        folder = cast("Folder | None", self.collection_instance)
        name = folder.name if folder else ""

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
            #
            # The ACL is the full one, so an ancestor only names itself
            # when it still holds a comic this user may see. An ancestor
            # whose whole subtree is above their age rating drops out of
            # the trail rather than leaking its name. ``distinct()``
            # because the rating and pending-delete clauses both ride
            # the multi-valued ``comic__`` hop.
            prefixes = [str(p) for p in PurePath(folder.path).parents]
            ancestors = {
                ancestor.path: ancestor
                for ancestor in FolderModel.objects.filter(
                    self.get_acl_filter(FolderModel, self.request.user),
                    library_id=folder.library_id,  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
                    path__in=prefixes,
                )
                .only("pk", "path", "name")
                .distinct()
            }
            # Nearest-first, and the walk stops at the first prefix that
            # does not resolve. Skipping it instead would hang the
            # current folder off its grandparent and present a trail
            # that never existed. The prefixes above the library root
            # never match a row, so this is also what ends the walk on
            # an ordinary browse.
            for prefix in prefixes:
                ancestor = ancestors.get(prefix)
                if not ancestor:
                    break
                crumbs.append(
                    Route(FOLDER_COLLECTION, (ancestor.pk,), 1, ancestor.name)
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
