"""Group Filters."""

from django.db.models import Q

from codex.views.const import (
    FILTER_ONLY_GROUP_RELATION,
    FOLDER_GROUP,
    GROUP_RELATION,
)
from codex.views.session import SessionView


class GroupFilterView(SessionView):
    """Group Filters."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    def _get_rel_for_pks(self, group, page_mtime=False):
        """Get the relation from the model to the pks."""
        # XXX these TARGET refs might be better as subclass get rel methods.
        target: str = self.TARGET  # type: ignore
        if target in ("cover", "choices"):
            rel = FILTER_ONLY_GROUP_RELATION[group]
        elif target in ("metadata", "mtime") or page_mtime:
            # metadata, mtime, browser.page_mtime
            rel = "pk"
        else:
            # browser.group, opds
            rel = GROUP_RELATION[group]

        rel += "__in"
        return rel

    def get_group_filter(self, group=None, pks=None, page_mtime=False):
        """Get filter for the displayed group."""
        if group is None:
            group = self.kwargs["group"]
        if pks is None:
            pks = self.kwargs["pks"]

        if pks and 0 not in pks:
            rel = self._get_rel_for_pks(group, page_mtime)
            group_filter_dict = {rel: pks}
        elif group == FOLDER_GROUP:
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}

        return Q(**group_filter_dict)
