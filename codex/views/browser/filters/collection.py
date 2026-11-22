"""Collection Filters."""

from typing import Final

from django.db.models.query_utils import Q

from codex.models import ReadingList
from codex.views.browser.params import BrowserParamsView
from codex.views.const import (
    COLLECTION_RELATION,
    FILTER_ONLY_COLLECTION_RELATION,
    FOLDER_COLLECTION,
    STORY_ARC_COLLECTION,
)

_COLLECTION_REL_TARGETS: Final = frozenset(
    {"cover", "choices", "bookmark", "force_update"}
)
_PK_REL_TARGETS: Final = frozenset({"metadata", "mtime"})


class CollectionFilterView(BrowserParamsView):
    """Collection Filters."""

    TARGET: str = ""

    def _get_rel_for_pks(self, collection, *, page_mtime: bool):
        """Get the relation from the model to the pks."""
        if self.TARGET in _COLLECTION_REL_TARGETS:
            rel = FILTER_ONLY_COLLECTION_RELATION[collection]
        elif self.TARGET in _PK_REL_TARGETS or page_mtime:
            # metadata, mtime, browser.page_mtime
            rel = "pk"
        elif self.TARGET == "download":
            rel = "comic__folders" if collection == FOLDER_COLLECTION else "pk"
        else:
            # browser.collection, opds
            rel = COLLECTION_RELATION[collection]

        rel += "__in"
        return rel

    def _reading_list_scope(self, rel: str) -> Q:
        """
        Scope a list's pks to the lists the user may see, shown entries only.

        One Q with the pks, so the tests ride the same join. On the lists
        themselves, the ACL filter skips hidden entries instead.
        """
        user = self.request.user
        target = rel.removesuffix("__in")
        if target == "pk":
            return self.reading_list_visibility_filter(user)
        entries_prefix = target.removesuffix("reading_list")
        return self.reading_list_entries_filter(user, entries_prefix)

    def is_lists_grid(self, model, collection=None, pks=None) -> bool:
        """
        Whether a query reads the grid of lists, not one list.

        ReadingList is the model for one list too: its page mtime, metadata
        and download. Filters that pick lists, not comics, apply on the grid
        only. ``collection`` and ``pks`` default to the route's, as for
        :meth:`get_collection_filter`; the mtime probe passes its own.
        """
        if model is not ReadingList:
            return False
        if collection is None:
            collection = self.kwargs.get("collection")
        if pks is None:
            pks = self.kwargs.get("pks")
        return collection == STORY_ARC_COLLECTION and not (pks and 0 not in pks)

    def get_collection_filter(
        self, collection=None, pks=None, *, page_mtime=False
    ) -> Q:
        """Get filter for the displayed collection."""
        if collection is None:
            collection = self.kwargs["collection"]
        if pks is None:
            pks = self.kwargs["pks"]

        if pks and 0 not in pks:
            rel = self._get_rel_for_pks(collection, page_mtime=page_mtime)
            collection_filter = Q(**{rel: pks})
            if collection == STORY_ARC_COLLECTION:
                collection_filter &= self._reading_list_scope(rel)
            return collection_filter
        if collection == FOLDER_COLLECTION and self.TARGET != "choices":
            # Top folder search
            return Q(parent_folder=None)
        return Q()
