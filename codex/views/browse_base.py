"""Views for browsing comic library."""
import logging

from django.db.models import Q
from rest_framework.views import APIView

from codex.models import Folder
from codex.views.mixins import SessionMixin


# from codex.views.mixins import UserBookmarkMixin

LOG = logging.getLogger(__name__)


class BrowseBaseView(APIView, SessionMixin):
    """Browse comics with a variety of filters and sorts."""

    FOLDER_GROUP = "f"
    GROUP_RELATION = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
        "c": "comic",
    }
    FILTER_ATTRIBUTES = ("decade", "characters")

    def filter_by_comic_many_attribute(self, attribute):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(attribute)
        filter_query = Q()
        if filter_list:
            # None values in a list don't work right so test for them
            #   seperately
            for index, val in enumerate(filter_list):
                if val is None:
                    del filter_list[index]
                    filter_query |= Q(**{f"comic__{attribute}": None})
            if filter_list:
                filter_query |= Q(**{f"comic__{attribute}__in": filter_list})
        return filter_query

    def get_comic_attribute_filter(self):
        """Filter the comics based on the form filters."""
        comic_attribute_filter = Q()
        for attribute in self.FILTER_ATTRIBUTES:
            comic_attribute_filter &= self.filter_by_comic_many_attribute(attribute)
        return comic_attribute_filter

    def get_bookmark_filter(self):
        """Build bookmark query."""
        choice = self.params["filters"].get("bookmark", "ALL")

        bookmark_filter = Q()
        if choice in (
            "UNREAD",
            "IN_PROGRESS",
        ):
            bookmark_filter &= (
                Q(comic__userbookmark__finished=False)
                | Q(comic__userbookmark=None)
                | Q(comic__userbookmark__finished=None)
            )
            if choice == "IN_PROGRESS":
                bookmark_filter &= Q(comic__userbookmark__bookmark__gt=0)
        return bookmark_filter

    def get_folders_filter(self):
        """Filters for ALL parent folders not just immediate one."""
        pk = self.kwargs.get("pk")
        if pk:
            folders_filter = Q(folder__in=[pk])
        else:
            folders_filter = Q()

        return folders_filter

    def get_parent_folder_filter(self):
        """Create the folder and comic object lists."""
        pk = self.kwargs.get("pk")
        if pk:
            self.host_folder = Folder.objects.select_related("parent_folder").get(pk=pk)
        else:
            self.host_folder = None

        return Q(parent_folder=self.host_folder)

    def get_browse_container_filter(self):
        """Get the objects we'll be displaying."""
        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        pk = self.kwargs.get("pk")
        if pk:
            group = self.kwargs.get("group")
            group_relation = self.GROUP_RELATION[group]
            container_filter = Q(**{group_relation: pk})
        else:
            container_filter = Q()

        return container_filter

    def get_query_filters(self, choices=False):
        """Return the main object filter and the one for aggregates."""
        # XXX This logic is complicated and confusing
        is_folder_view = self.kwargs.get("group") == self.FOLDER_GROUP
        if is_folder_view:
            if choices:
                object_filter = self.get_folders_filter()
            else:
                object_filter = self.get_parent_folder_filter()
        else:
            object_filter = self.get_browse_container_filter()

        if is_folder_view or not choices:
            bookmark_filter_join = self.get_bookmark_filter()
            comic_attribute_filter = self.get_comic_attribute_filter()
            aggregate_filter = bookmark_filter_join & comic_attribute_filter
        else:
            aggregate_filter = None
        if is_folder_view:
            object_filter &= aggregate_filter

        return object_filter, aggregate_filter
