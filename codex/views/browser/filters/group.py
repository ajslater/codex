"""Group Filters."""

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


class GroupFilterView(BrowserParamsView):
    """Group Filters."""

    TARGET: str = ""

    def _get_rel_for_pks(self, group, *, page_mtime: bool):
        """Get the relation from the model to the pks."""
        if self.TARGET in _COLLECTION_REL_TARGETS:
            rel = FILTER_ONLY_COLLECTION_RELATION[group]
        elif self.TARGET in _PK_REL_TARGETS or page_mtime:
            # metadata, mtime, browser.page_mtime
            rel = "pk"
        elif self.TARGET == "download":
            rel = "comic__folders" if group == FOLDER_COLLECTION else "pk"
        else:
            # browser.group, opds
            rel = COLLECTION_RELATION[group]

        rel += "__in"
        return rel

    def get_group_filter(self, group=None, pks=None, *, page_mtime=False) -> Q:
        """Get filter for the displayed group."""
        if group is None:
            group = self.kwargs["group"]
        if pks is None:
            pks = self.kwargs["pks"]

        if pks and 0 not in pks:
            rel = self._get_rel_for_pks(group, page_mtime=page_mtime)
            group_filter_dict = {rel: pks}
        elif group == FOLDER_COLLECTION and self.TARGET != "choices":
            # Top folder search
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}
        return Q(**group_filter_dict)
