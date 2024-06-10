"""Group Filters."""

from django.db.models import Q

from codex.models import Comic
from codex.views.const import FOLDER_GROUP, GROUP_RELATION
from codex.views.session import SessionView


class GroupFilterView(SessionView):
    """Group Filters."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    def get_group_filter(self, model, group=None, pks=None):
        """Get filter for the displayed group."""
        if group is None:
            group = self.kwargs["group"]
        if pks is None:
            pks = self.kwargs["pks"]

        if pks and 0 not in pks:  # type: ignore
            target: str = self.TARGET  # type: ignore
            if (
                target in frozenset({"choices", "cover"})
                and model == Comic
                and group == FOLDER_GROUP
            ):
                rel = "folders"
            elif target in frozenset({"metadata", "mtime"}) or (
                target == "cover" and model != Comic
            ):
                rel = "pk"
            else:
                rel = GROUP_RELATION[group]

            rel += "__in"
            group_filter_dict = {rel: pks}  # type: ignore
        elif group == FOLDER_GROUP:
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}

        return Q(**group_filter_dict)
