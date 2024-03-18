"""Group Filters."""

from django.db.models import Q

from codex.views.auth import GroupACLMixin


class GroupFilterMixin(GroupACLMixin):
    """Group Filters."""

    def get_group_filter(self, choices):
        """Get filter for the displayed group."""
        pk = self.kwargs.get("pk")  # type: ignore
        group = self.kwargs.get("group")  # type: ignore
        if pk:
            group_relation = "comic__" if choices else ""
            if choices and group == self.FOLDER_GROUP:
                group_relation += "folders"
            else:
                group_relation += self.GROUP_RELATION[group]
            group_filter = Q(**{group_relation: pk})
        elif group == self.FOLDER_GROUP:
            group_filter = Q(parent_folder=None)
        else:
            group_filter = Q()

        return group_filter
