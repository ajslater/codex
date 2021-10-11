"""Views for browsing comic library."""
import logging

from django.core.paginator import EmptyPage, Paginator
from django.db.models import CharField, Count, F, IntegerField, Value
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from stringcase import snakecase

from codex.librarian.latest_version import get_installed_version, get_latest_version
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.serializers.browser import (
    BrowserOpenedSerializer,
    BrowserPageSerializer,
    BrowserSettingsSerializer,
)
from codex.settings.settings import CACHE_PATH
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBase


PACKAGE_NAME = "codex"
LOG = logging.getLogger(__name__)


class BrowserView(BrowserMetadataBase):
    """Browse comics with a variety of filters and sorts."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    GROUP_SHOW_FLAGS = {
        # Show flags to root group equivalients
        "r": "p",
        "p": "i",
        "i": "s",
        "s": "v",
        "v": "c",
    }
    MAX_OBJ_PER_PAGE = 100
    ORPHANS = MAX_OBJ_PER_PAGE / 20
    BROWSER_CARD_FIELDS = [
        "bookmark",
        "child_count",
        "display_name",
        "finished",
        "group",
        "header_name",
        "library",
        "order_value",
        "pk",
        "progress",
        "series_name",
        "volume_name",
        "x_cover_path",
        "x_issue",
        "x_path",
    ]

    def get_valid_root_groups(self):
        """
        Get valid root groups for the current settings.

        Valid root groups are determined by the Browser Settings.
        And offset by one group *above* each show flag.
        The volumes root group is always enabled.
        """
        valid_groups = []

        for group_key, show_flag in self.GROUP_SHOW_FLAGS.items():
            enabled = group_key == "v"
            enabled = enabled or self.params["show"].get(show_flag)
            if enabled:
                valid_groups.append(group_key)

        return valid_groups

    def get_valid_nav_groups(self):
        """
        Get valid nav gorups for the current settings.

        Valid nav groups are the root group and below that are also
        enabled in browser settings.
        """
        root_group = self.params["root_group"]
        valid_groups = []
        below_root_group = False

        for group_key in self.GROUP_SHOW_FLAGS:
            if group_key == root_group:
                enabled = below_root_group = True
            else:
                enabled = below_root_group and self.params["show"].get(group_key)
            if enabled:
                valid_groups.append(group_key)

        return valid_groups

    def get_model_group(self):
        """
        Get the model group code for the current model.

        Valid model groups are below the nav group that are also enabled
        in browser settings.
        """
        nav_group = self.kwargs["group"]

        if nav_group == self.FOLDER_GROUP:
            return nav_group

        below_nav_group = False

        for group_key in self.valid_nav_groups:
            if below_nav_group and self.params["show"].get(group_key):
                return group_key
            if group_key == nav_group:
                below_nav_group = True

        return self.COMIC_GROUP

    def add_annotations(self, obj_list, model, aggregate_filter):
        """
        Annotations for display and sorting.

        model is neccissary because this gets called twice by folder
        view. once for folders, once for the comics.
        """
        ##########################################
        # Annotate children count and page count #
        ##########################################
        obj_list = self.annotate_page_count(obj_list, aggregate_filter)
        # EXTRA FILTER for empty group
        child_count_sum = Count("comic__pk", distinct=True, filter=aggregate_filter)
        obj_list = obj_list.annotate(child_count=child_count_sum).filter(
            child_count__gt=0
        )

        ##################
        # Annotate Group #
        ##################
        self.model_group = self.GROUP_MODEL.inverse[model]
        obj_list = obj_list.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )

        ################################
        # Annotate userbookmark hoists #
        ################################
        obj_list = self.annotate_bookmarks(obj_list)

        #####################
        # Annotate progress #
        #####################
        obj_list = self.annotate_progress(obj_list)

        #######################
        # Annotate Library Id #
        #######################
        if model not in (Folder, Comic):
            # For folder view stability sorting compatibilty
            obj_list = obj_list.annotate(library=Value(0, IntegerField()))

        #######################
        # Sortable aggregates #
        #######################
        sort_by = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)
        order_func = self.get_aggregate_func(sort_by, model, aggregate_filter)
        obj_list = obj_list.annotate(order_value=order_func)

        #######################
        # Annotate Cover Path #
        #######################
        obj_list = self.annotate_cover_path(
            obj_list,
            model,
            aggregate_filter,
        )

        #######################
        # Annotate name fields #
        #######################
        # XXX header_name & display_name could be done on import.
        if model in (Publisher, Series, Folder, Comic):
            header_name = Value(None, CharField())
        elif model == Imprint:
            header_name = F("publisher__name")
        elif model == Volume:
            header_name = F("series__name")
        else:
            header_name = ""

        if model == Comic:
            series_name = F("series__name")
            volume_name = F("volume__name")
            x_issue = F("issue")
            x_path = F("path")
        else:
            series_name = Value(None, CharField())
            volume_name = Value(None, CharField())
            x_issue = Value(None, CharField())
            x_path = Value(None, CharField())

        # XXX should group use title or comics use name?
        # if model in (Publisher, Imprint, Series, Volume, Folder):
        #    display_name = F("name")
        if model == Comic:
            display_name = F("title")
        else:
            display_name = F("name")

        obj_list = obj_list.annotate(
            header_name=header_name,
            series_name=series_name,
            volume_name=volume_name,
            x_issue=x_issue,
            x_path=x_path,
            display_name=display_name,
        )

        return obj_list

    def set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs.get("group")
        self.group_class = self.GROUP_MODEL[group]

        model_group = self.get_model_group()
        self.model = self.GROUP_MODEL[model_group]

    def get_folder_queryset(self, object_filter, aggregate_filter):
        """Create folder queryset."""
        # Create the main queries with filters
        folder_list = Folder.objects.filter(object_filter)
        comic_list = Comic.objects.filter(object_filter)

        # add annotations for display and sorting
        # and the comic_cover which uses a sort
        folder_list = self.add_annotations(folder_list, Folder, aggregate_filter)
        comic_list = self.add_annotations(comic_list, Comic, aggregate_filter)

        # Reduce to values for concatenation
        folder_list = folder_list.values(*self.BROWSER_CARD_FIELDS)
        comic_list = comic_list.values(*self.BROWSER_CARD_FIELDS)
        obj_list = folder_list.union(comic_list)

        return obj_list

    def get_browser_group_queryset(self, object_filter, aggregate_filter):
        """Create and browse queryset."""
        obj_list = self.model.objects.filter(object_filter)
        # obj_list filtering done

        # Add annotations for display and sorting
        obj_list = self.add_annotations(obj_list, self.model, aggregate_filter)

        # Convert to a dict to be compatible with Folder View concatenate
        obj_list = obj_list.values(*self.BROWSER_CARD_FIELDS)

        return obj_list

    def get_folder_up_route(self):
        """Get out parent's pk."""
        up_group = self.FOLDER_GROUP
        up_pk = None

        # Recall root id & relative path from way back in
        # object creation
        if self.host_folder:
            if self.host_folder.parent_folder:
                up_pk = self.host_folder.parent_folder.pk
            else:
                up_pk = 0

        return up_group, up_pk

    def set_group_instance(self):
        """Create group_class instance."""
        pk = self.kwargs.get("pk")
        group = self.kwargs.get("group")
        if pk == 0:
            self.group_instance = None
        elif group == self.FOLDER_GROUP:
            self.group_instance = self.host_folder
        else:
            self.group_instance = self.group_class.objects.select_related().get(pk=pk)

    def get_browse_up_route(self):
        """Get the up route from the first valid ancestor."""
        group = self.kwargs.get("group")

        # Ancestor group
        ancestor_group = None
        for group_key in self.valid_nav_groups:
            if group_key == group:
                break
            ancestor_group = group_key

        up_group = ancestor_group
        up_pk = None

        # Ancestor pk
        # pk == 0 for special instances where we're displaying 0 but there
        #  is still a parent who should also be 0
        pk = self.kwargs.get("pk")
        if up_group == self.params["root_group"] or pk == 0:
            up_pk = 0
        elif up_group is not None:
            # get the ancestor pk from the current group
            up_relation = self.GROUP_RELATION[up_group]
            up_pk = getattr(self.group_instance, up_relation).pk

        return up_group, up_pk

    def get_browser_page_title(self):
        """Get the proper title for this browse level."""
        pk = self.kwargs.get("pk")
        parent_name = None
        group_count = 0
        group_name = None
        if pk == 0:
            group_name = self.model._meta.verbose_name_plural.capitalize()
        elif self.group_instance:
            if self.group_class == Imprint:
                parent_name = self.group_instance.publisher.name
            elif self.group_class == Volume:
                parent_name = self.group_instance.series.name
                group_count = self.group_instance.series.volume_count

            group_name = self.group_instance.name

        browser_page_title = {
            "parentName": parent_name,
            "groupName": group_name,
            "groupCount": group_count,
        }

        return browser_page_title

    def raise_valid_route(self, message):
        """403 should redirect to the valid group on the client side."""
        valid_group = self.valid_nav_groups[0]
        raise PermissionDenied({"group": valid_group, "message": message})

    def validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        enable_folder_view = (
            AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW).on
        )
        if not enable_folder_view:
            self.valid_nav_groups = self.get_valid_nav_groups()
            self.raise_valid_route("folder view disabled")

    def validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        # Validate Root Group
        group = self.kwargs["group"]
        root_group = self.params.get("root_group")
        if root_group == self.FOLDER_GROUP:
            self.params["root_group"] = root_group = group
            LOG.warn(f"Switched root group from {self.FOLDER_GROUP} to {group}")
        else:
            valid_root_groups = self.get_valid_root_groups()
            if root_group not in valid_root_groups:
                if group in valid_root_groups:
                    self.params["root_group"] = root_group = group
                else:
                    self.params["root_group"] = valid_root_groups[0]
                LOG.warn(f"Reset root group to {self.params['root_group']}")

        # Validate Group
        self.valid_nav_groups = self.get_valid_nav_groups()
        if group not in self.valid_nav_groups:
            self.raise_valid_route(f"Asked to show disabled group {group}")
        if group == "r" and self.kwargs["pk"]:
            self.raise_valid_route(f"Cannot show group {group} with pk other than 0.")

    def validate_put(self, data):
        """Validate submitted settings."""
        serializer = BrowserSettingsSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as ex:
            LOG.error(serializer.errors)
            LOG.exception(ex)
            raise ex

        self.params = {}
        for key, value in serializer.validated_data.items():
            snake_key = snakecase(key)
            self.params[snake_key] = value

    def get_browser_page(self):
        """Validate settings and get the querysets."""
        if self.kwargs.get("group") == self.FOLDER_GROUP:
            self.validate_folder_settings()
        else:
            self.validate_browser_group_settings()

        self.set_browse_model()
        # Create the main query with the filters
        object_filter, aggregate_filter = self.get_query_filters()

        if self.kwargs.get("group") == self.FOLDER_GROUP:
            obj_list = self.get_folder_queryset(object_filter, aggregate_filter)
        else:
            obj_list = self.get_browser_group_queryset(object_filter, aggregate_filter)

        # Order
        order_by = self.get_order_by(self.model, True)
        obj_list = obj_list.order_by(*order_by)

        # Pagination
        paginator = Paginator(obj_list, self.MAX_OBJ_PER_PAGE, orphans=self.ORPHANS)
        page = self.kwargs.get("page")
        if page < 1:
            page = 1
        try:
            obj_list = paginator.page(page).object_list
        except EmptyPage:
            LOG.warn("No items on page {page}")
            obj_list = paginator.page(1).object_list

        self.request.session[self.BROWSER_KEY] = self.params
        self.request.session.save()

        # get additional context
        self.set_group_instance()
        if self.kwargs.get("group") == self.FOLDER_GROUP:
            up_group, up_pk = self.get_folder_up_route()
        else:
            up_group, up_pk = self.get_browse_up_route()
        browser_page_title = self.get_browser_page_title()

        if up_group is not None and up_pk is not None:
            up_route = {"group": up_group, "pk": up_pk, "page": 1}
        else:
            up_route = {}

        efv_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW)

        libraries_exist = Library.objects.exists()

        # construct final data structure
        browser_page = {
            "upRoute": up_route,
            "browserTitle": browser_page_title,
            "modelGroup": self.model_group,
            "objList": obj_list,
            "numPages": paginator.num_pages,
            "formChoices": {"enableFolderView": efv_flag.on},
            "librariesExist": libraries_exist,
        }
        return browser_page

    def put(self, request, *args, **kwargs):
        """Create the view."""
        self.validate_put(request.data)

        browser_page = self.get_browser_page()

        serializer = BrowserPageSerializer(browser_page)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self.params = self.get_session(self.BROWSER_KEY)

        browser_page = self.get_browser_page()

        filters = self.params["filters"]

        installed_version = get_installed_version(PACKAGE_NAME)
        latest_version = get_latest_version(PACKAGE_NAME, cache_root=CACHE_PATH)

        data = {
            "settings": {
                "filters": filters,
                "rootGroup": self.params.get("root_group"),
                "sortBy": self.params.get("sort_by"),
                "sortReverse": self.params.get("sort_reverse"),
                "show": self.params.get("show"),
            },
            "browserPage": browser_page,
            "versions": {"installed": installed_version, "latest": latest_version},
        }

        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
