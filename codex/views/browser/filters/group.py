"""Group Filters."""
from django.db.models import Q

from codex.views.mixins import GroupACLMixin


class GroupFilterMixin(GroupACLMixin):
    """Group Filters."""

    def _get_folders_filter(self):
        """Get a filter for ALL parent folders not just immediate one."""
        pk = self.kwargs.get("pk")  # type: ignore
        return Q(folders__in=[pk]) if pk else Q()

    def _get_browser_group_filter(self):
        """Get the objects we'll be displaying."""
        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        group_filter = Q()
        pk = self.kwargs.get("pk")  # type: ignore
        group = self.kwargs.get("group")  # type: ignore
        if pk or group == self.FOLDER_GROUP:
            if not pk:
                pk = None
            group_relation = self.GROUP_RELATION[group]
            group_filter |= Q(**{group_relation: pk})

        return group_filter

    def get_group_filter(self, choices):
        """Get filter for the displayed group."""
        group = self.kwargs.get("group")  # type: ignore
        if group == self.FOLDER_GROUP and choices:
            # Choice view needs to get all descendant comic attributes
            # So filter by all the folders
            group_filter = self._get_folders_filter()
        elif choices:
            group_filter = Q()
        else:
            # The browser filter is the same for all views
            group_filter = self._get_browser_group_filter()

        return group_filter
