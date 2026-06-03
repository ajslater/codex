"""Collection Filters."""

from typing import Final

from django.db.models.query_utils import Q

from codex.views.browser.params import BrowserParamsView
from codex.views.const import (
    COLLECTION_RELATION,
    FILTER_ONLY_COLLECTION_RELATION,
    FOLDER_COLLECTION,
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
            collection_filter_dict = {rel: pks}
        elif collection == FOLDER_COLLECTION and self.TARGET != "choices":
            # Top folder search
            collection_filter_dict = {"parent_folder": None}
        else:
            collection_filter_dict = {}
        return Q(**collection_filter_dict)
