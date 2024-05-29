"""Group Filters."""

from django.db.models import Q

from codex.views.auth import GroupACLMixin
from codex.views.const import FOLDER_GROUP, GROUP_RELATION


class GroupFilterMixin(GroupACLMixin):
    """Group Filters."""

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
