"""Views for browsing comic library."""
from logging import getLogger

from bidict import bidict  # type: ignore
from django.db.models import Q

from codex.models import Comic, Folder, Imprint, Publisher, Series, Volume
from codex.views.mixins import SessionMixin


LOG = getLogger(__name__)


class BrowserBaseView(SessionMixin):
    """Browse comics with a variety of filters and sorts."""

    COMIC_GROUP = "c"
    FOLDER_GROUP = "f"
    GROUP_MODEL = bidict(
        {
            "r": None,
            "p": Publisher,
            "i": Imprint,
            "s": Series,
            "v": Volume,
            COMIC_GROUP: Comic,
            FOLDER_GROUP: Folder,
        }
    )
    GROUP_RELATION = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
    }

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        self.params = {}
        super().__init__(*args, **kwargs)

    def filter_by_comic_field(self, field, is_model_comic):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(field)
        filter_query = Q()
        if filter_list:
            if is_model_comic:
                query_prefix = ""
            else:
                query_prefix = "comic__"

            # None values in a list don't work right so test for them
            #   separately
            for index, val in enumerate(filter_list):
                if val is None:
                    del filter_list[index]
                    filter_query |= Q(**{f"{query_prefix}{field}__isnull": True})
            if filter_list:
                if field == self.CREDIT_PERSON_UI_FIELD:
                    rel = f"{query_prefix}credits__person__in"
                else:
                    rel = f"{query_prefix}{field}__in"
                filter_query |= Q(**{rel: filter_list})
        return filter_query

    def get_comic_field_filter(self, is_model_comic):
        """Filter the comics based on the form filters."""
        comic_field_filter = Q()
        for attribute in self.FILTER_ATTRIBUTES:
            comic_field_filter &= self.filter_by_comic_field(attribute, is_model_comic)
        return comic_field_filter

    def get_ubm_rel(self, is_model_comic):
        """Create userbookmark relation."""
        ubm_rel = "userbookmark"
        if not is_model_comic:
            ubm_rel = "comic__" + ubm_rel
        return ubm_rel

    def get_bookmark_filter(self, is_model_comic):
        """Build bookmark query."""
        choice = self.params["filters"].get("bookmark", "ALL")

        bookmark_filter = Q()
        if choice in (
            "UNREAD",
            "IN_PROGRESS",
        ):
            ubm_rel = self.get_ubm_rel(is_model_comic)

            bookmark_filter &= (
                Q(**{f"{ubm_rel}__finished": False})
                | Q(**{ubm_rel: None})
                | Q(**{f"{ubm_rel}__finished": None})
            )
            if choice == "IN_PROGRESS":
                bookmark_filter &= Q(**{f"{ubm_rel}__bookmark__gt": 0})
        return bookmark_filter

    def get_folders_filter(self):
        """Get a filter for ALL parent folders not just immediate one."""
        pk = self.kwargs.get("pk")
        if pk:
            folders_filter = Q(folders__in=[pk])
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

    def get_browser_group_filter(self):
        """Get the objects we'll be displaying."""
        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        group_filter = Q()
        pk = self.kwargs.get("pk")
        if pk:
            group = self.kwargs.get("group")
            group_relation = self.GROUP_RELATION[group]
            group_filter |= Q(**{group_relation: pk})

        return group_filter

    def get_aggregate_filter(self, is_model_comic):
        """Return the filter for making aggregates."""
        bookmark_filter_join = self.get_bookmark_filter(is_model_comic)
        comic_field_filter = self.get_comic_field_filter(is_model_comic)
        aggregate_filter = bookmark_filter_join & comic_field_filter
        return aggregate_filter

    def get_query_filters(self, is_model_comic, choices=False):
        """Return the main object filter and the one for aggregates."""
        is_folder_view = self.kwargs.get("group") == self.FOLDER_GROUP
        if is_folder_view:
            if choices:
                # Choice view needs to get all descendant comic attributes
                # So filter by all the folders
                object_filter = self.get_folders_filter()
            else:
                # Regular browsing just needs to filter by the parent
                object_filter = self.get_parent_folder_filter()
        else:
            # The browser filter is the same for all views
            object_filter = self.get_browser_group_filter()

        aggregate_filter = self.get_aggregate_filter(is_model_comic)
        object_filter &= aggregate_filter
        return object_filter
