"""Views for browsing comic library."""
from logging import getLogger

from django.core.paginator import EmptyPage, Paginator
from django.db.models import CharField, F, IntegerField, Value
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from stringcase import snakecase

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, BulkComicCoverCreateTask
from codex.models import AdminFlag, Comic, Folder, Imprint, Library, Volume
from codex.serializers.browser import (
    BrowserOpenedSerializer,
    BrowserPageSerializer,
    BrowserSettingsSerializer,
)
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.version import PACKAGE_NAME, VERSION, get_latest_version
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBase


LOG = getLogger(__name__)


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
    ORPHANS = int(MAX_OBJ_PER_PAGE / 20)
    BROWSER_CARD_FIELDS = [
        "bookmark",
        "child_count",
        f"{UNIONFIX_PREFIX}cover_path",
        "finished",
        "group",
        f"{UNIONFIX_PREFIX}issue",
        "library",
        "name",
        "order_value",
        "path",
        "pk",
        "progress",
        "publisher_name",
        "series_name",
        "volume_name",
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

    def add_annotations(self, obj_list, model):
        """
        Annotations for display and sorting.

        model is neccissary because this gets called twice by folder
        view. once for folders, once for the comics.
        """
        is_model_comic = model == Comic
        ##############################
        # Annotate Common Aggregates #
        ##############################
        obj_list = self.annotate_common_aggregates(obj_list, model)
        if not is_model_comic:
            # EXTRA FILTER for empty group
            obj_list = obj_list.filter(child_count__gt=0)

        ##################
        # Annotate Group #
        ##################
        self.model_group = self.GROUP_MODEL.inverse[model]
        obj_list = obj_list.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )

        #######################
        # Annotate Library Id #
        #######################
        if model not in (Folder, Comic):
            # For folder view stability sorting compatibility
            obj_list = obj_list.annotate(library=Value(0, IntegerField()))

        #######################
        # Sortable aggregates #
        #######################
        sort_by = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)
        order_func = self.get_aggregate_func(sort_by, is_model_comic)
        obj_list = obj_list.annotate(order_value=order_func)

        ########################
        # Annotate name fields #
        ########################
        publisher_name = Value(None, CharField())
        series_name = Value(None, CharField())
        volume_name = Value(None, CharField())

        if is_model_comic:
            series_name = F("series__name")
            volume_name = F("volume__name")
        elif model == Imprint:
            publisher_name = F("publisher__name")
        elif model == Volume:
            series_name = F("series__name")

        obj_list = obj_list.annotate(
            publisher_name=publisher_name,
            series_name=series_name,
            volume_name=volume_name,
        )
        if is_model_comic:
            issue = F("issue")
        else:
            issue = Value(None, IntegerField())
        obj_list = obj_list.annotate(
            **{f"{UNIONFIX_PREFIX}issue": issue},
        )
        if model not in (Folder, Comic):
            path = Value(None, CharField())
            obj_list = obj_list.annotate(
                path=path,
            )

        return obj_list

    def set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs.get("group")
        self.group_class = self.GROUP_MODEL[group]

        model_group = self.get_model_group()
        self.model = self.GROUP_MODEL[model_group]

    def get_folder_queryset(self, object_filter):
        """Create folder queryset."""
        # Create the main queries with filters
        folder_list = Folder.objects.filter(object_filter)
        comic_object_filter = self.get_query_filters(True, False)
        comic_list = Comic.objects.filter(comic_object_filter)

        # add annotations for display and sorting
        # and the comic_cover which uses a sort
        folder_list = self.add_annotations(folder_list, Folder)
        comic_list = self.add_annotations(comic_list, Comic)

        # Reduce to values to make union align columns correctly
        folder_list = folder_list.values(*self.BROWSER_CARD_FIELDS)
        comic_list = comic_list.values(*self.BROWSER_CARD_FIELDS)

        obj_list = folder_list.union(comic_list)
        return obj_list

    def get_browser_group_queryset(self, object_filter):
        """Create and browse queryset."""
        if not self.model:
            raise ValueError("No model set in browser")

        obj_list = self.model.objects.filter(object_filter)
        # obj_list filtering done

        # Add annotations for display and sorting
        obj_list = self.add_annotations(obj_list, self.model)

        # Convert to a dict because otherwise the folder/comic union blowsy
        # up the paginator
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
            if not self.group_class:
                raise ValueError("No group_class set in browser")
            try:
                self.group_instance = self.group_class.objects.select_related().get(
                    pk=pk
                )
            except self.group_class.DoesNotExist:
                self.raise_valid_route(f"{group}={pk} Does not exist!", False)

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
            if not self.model:
                raise ValueError("No model set in browser")
            plural = self.model._meta.verbose_name_plural
            if not plural:
                raise ValueError(f"No plural name for {self.model}")
            group_name = plural.capitalize()
        elif self.group_instance:
            if isinstance(self.group_instance, Imprint):
                parent_name = self.group_instance.publisher.name
            elif isinstance(self.group_instance, Volume):
                parent_name = self.group_instance.series.name
                group_count = self.group_instance.series.volume_count
            elif isinstance(self.group_instance, Comic):
                group_count = self.group_instance.volume.issue_count
            elif isinstance(self.group_instance, Folder):
                parent_folder = self.group_instance.parent_folder
                if parent_folder:
                    prefix = parent_folder.library.path
                    if prefix[-1] != "/":
                        prefix += "/"
                    parent_name = parent_folder.path.removeprefix(prefix)

            group_name = self.group_instance.name

        browser_page_title = {
            "parentName": parent_name,
            "groupName": group_name,
            "groupCount": group_count,
        }

        return browser_page_title

    def raise_valid_route(self, message, permission_denied=True):
        """403 should redirect to the valid group on the client side."""
        group = self.kwargs["group"]
        if group == "f":
            valid_group = group
        else:
            valid_group = self.valid_nav_groups[0]
        detail = {"group": valid_group, "message": message}
        if permission_denied:
            raise PermissionDenied(detail)
        else:
            raise NotFound(detail)

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
        valid_root_groups = self.get_valid_root_groups()
        if root_group not in valid_root_groups:
            if group in valid_root_groups:
                self.params["root_group"] = group
            else:
                self.params["root_group"] = valid_root_groups[0]
            LOG.verbose(  # type: ignore
                f"Reset root group from {root_group} to {self.params['root_group']}"
            )

        # Validate Group
        self.valid_nav_groups = self.get_valid_nav_groups()
        if group not in self.valid_nav_groups:
            self.raise_valid_route(f"Asked to show disabled group {group}")
        if group == "r" and self.kwargs["pk"]:
            self.raise_valid_route(f"Cannot show group {group} with pk other than 0.")

    def apply_put(self, data):
        """Validate submitted settings."""
        serializer = BrowserSettingsSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            LOG.error(serializer.errors)
            LOG.exception(exc)
            raise exc

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
        try:
            object_filter = self.get_query_filters(self.model == Comic, False)
        except Folder.DoesNotExist:
            pk = self.kwargs.get("pk")
            self.raise_valid_route(f"f={pk} Does not exist!", False)
        group = self.kwargs.get("group")

        if group == self.FOLDER_GROUP:
            obj_list = self.get_folder_queryset(object_filter)
        else:
            obj_list = self.get_browser_group_queryset(object_filter)

        # Order
        order_by, order_keys = self.get_order_by(self.model, True)
        obj_list = obj_list.order_by(*order_by)

        # Pagination
        paginator = Paginator(obj_list, self.MAX_OBJ_PER_PAGE, orphans=self.ORPHANS)
        page = min(self.kwargs.get("page", 1), 1)
        try:
            obj_list = paginator.page(page).object_list
        except EmptyPage:
            LOG.warning(f"No items on page {page}")
            obj_list = paginator.page(1).object_list

        # Ensure comic covers exist for all browser cards
        if group == self.FOLDER_GROUP:
            # trimming the union query further breaks alignment
            comic_cover_tuple = obj_list
        else:
            comic_cover_tuple = obj_list.values(
                "path", f"{UNIONFIX_PREFIX}cover_path", *order_keys
            )
        task = BulkComicCoverCreateTask(False, comic_cover_tuple)  # type: ignore
        LIBRARIAN_QUEUE.put_nowait(task)

        # Save the session
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
        self.params = self.get_session(self.BROWSER_KEY)
        self.apply_put(request.data)

        browser_page = self.get_browser_page()

        serializer = BrowserPageSerializer(browser_page)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self.params = self.get_session(self.BROWSER_KEY)

        browser_page = self.get_browser_page()

        filters = self.params["filters"]
        latest_version = get_latest_version(PACKAGE_NAME)

        data = {
            "settings": {
                "filters": filters,
                "rootGroup": self.params.get("root_group"),
                "sortBy": self.params.get("sort_by"),
                "sortReverse": self.params.get("sort_reverse"),
                "show": self.params.get("show"),
            },
            "browserPage": browser_page,
            "versions": {"installed": VERSION, "latest": latest_version},
        }
        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
