"""Group Filters."""

from django.db.models import Q

from codex.views.const import FOLDER_GROUP, GROUP_RELATION
from codex.views.session import SessionView


class GroupFilterView(SessionView):
    """Group Filters."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    def get_group_filter(self, choices):
        """Get filter for the displayed group."""
        group = self.kwargs["group"]  # type: ignore
        pks = self.kwargs["pks"]  # type: ignore
        if pks:  # type: ignore
            group_relation = "comic__" if choices else ""
            if choices and group == FOLDER_GROUP:
                group_relation += "folders"
            else:
                group_relation += GROUP_RELATION[group]
            group_relation += "__in"
            group_filter_dict = {group_relation: pks}  # type: ignore
        elif group == FOLDER_GROUP:
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}

        return Q(**group_filter_dict)
