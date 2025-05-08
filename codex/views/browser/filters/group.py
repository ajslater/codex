"""Group Filters."""

from django.db.models import Q

from codex.views.browser.params import BrowserParamsView
from codex.views.const import (
    FILTER_ONLY_GROUP_RELATION,
    FOLDER_GROUP,
    GROUP_RELATION,
)

_GROUP_REL_TARGETS = frozenset({"cover", "choices", "bookmark"})
_PK_REL_TARGETS = frozenset({"metadata", "mtime"})


class GroupFilterView(BrowserParamsView):
    """Group Filters."""

    SESSION_KEY: str = BrowserParamsView.BROWSER_SESSION_KEY

    TARGET: str = ""

    def _get_rel_for_pks(self, group, *, page_mtime: bool):
        """Get the relation from the model to the pks."""
        if self.TARGET in _GROUP_REL_TARGETS:
            rel = FILTER_ONLY_GROUP_RELATION[group]
        elif self.TARGET in _PK_REL_TARGETS or page_mtime:
            # metadata, mtime, browser.page_mtime
            rel = "pk"
        elif self.TARGET == "download":
            rel = "comic__folders" if group == "f" else "pk"
        else:
            # browser.group, opds
            rel = GROUP_RELATION[group]

        rel += "__in"
        return rel

    def get_group_filter(self, group=None, pks=None, *, page_mtime=False):
        """Get filter for the displayed group."""
        if group is None:
            group = self.kwargs["group"]
        if pks is None:
            pks = self.kwargs["pks"]

        if pks and 0 not in pks:
            rel = self._get_rel_for_pks(group, page_mtime=page_mtime)
            group_filter_dict = {rel: pks}
        elif group == FOLDER_GROUP and self.TARGET != "choices":
            # Top folder search
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}
        return Q(**group_filter_dict)
