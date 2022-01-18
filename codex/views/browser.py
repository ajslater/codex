"""Views for browsing comic library."""
from copy import deepcopy
from logging import getLogger

from django.core.paginator import EmptyPage, Paginator
from django.db.models import CharField, F, IntegerField, Value
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from stringcase import camelcase

from codex.exceptions import SeeOtherRedirectError
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, BulkComicCoverCreateTask
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    SearchQuery,
    Series,
    Volume,
)
from codex.serializers.browser import (
    BrowserOpenedSerializer,
    BrowserPageSerializer,
    BrowserSettingsSerializer,
)
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.version import PACKAGE_NAME, VERSION, get_latest_version
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBaseView


LOG = getLogger(__name__)


class BrowserView(BrowserMetadataBaseView):
    """Browse comics with a variety of filters and sorts."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    _MODEL_GROUP_MAP = {
        v: k for k, v in BrowserMetadataBaseView.GROUP_MODEL_MAP.items()
    }
    _NAV_GROUPS = "rpisv"
    _MAX_OBJ_PER_PAGE = 100
    _ORPHANS = int(_MAX_OBJ_PER_PAGE / 20)
    _BROWSER_CARD_FIELDS = [
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
        "sort_name",
        "volume_name",
    ]
    _BROWSER_SETTINGS_KEYS_SNAKE_CAMEL_MAP = {
        snake_key: camelcase(snake_key)
        for snake_key in BrowserMetadataBaseView.SESSION_DEFAULTS[
            BrowserMetadataBaseView.BROWSER_KEY
        ].keys()
    }
    _BROWSER_SETTINGS_KEYS_CAMEL_SNAKE_MAP = {
        v: k for k, v in _BROWSER_SETTINGS_KEYS_SNAKE_CAMEL_MAP.items()
    }
    _NONE_CHARFIELD = Value(None, CharField())

    _GROUP_INSTANCE_SELECT_RELATED = {
        Comic: ("series", "volume"),
        Volume: ("series",),
        Series: (None,),
        Imprint: ("publisher",),
        Publisher: (None,),
    }
    _DEFAULT_ROUTE = {
        "name": "browser",
        "params": BrowserMetadataBaseView.SESSION_DEFAULTS[
            BrowserMetadataBaseView.BROWSER_KEY
        ]["route"],
    }

    def _add_annotations(self, queryset, model, autoquery_pk):
        """
        Annotations for display and sorting.

        model is neccissary because this gets called twice by folder
        view. once for folders, once for the comics.
        """
        is_model_comic = model == Comic
        ##############################
        # Annotate Common Aggregates #
        ##############################
        queryset = self.annotate_common_aggregates(queryset, model)
        if not is_model_comic:
            # EXTRA FILTER for empty group
            queryset = queryset.filter(child_count__gt=0)

        ##################
        # Annotate Group #
        ##################
        self.model_group = self._MODEL_GROUP_MAP[model]
        queryset = queryset.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )

        #######################
        # Annotate Library Id #
        #######################
        if model not in (Folder, Comic):
            # For folder view stability sorting compatibility
            queryset = queryset.annotate(library=Value(0, IntegerField()))

        #######################
        # Sortable aggregates #
        #######################
        order_by = self.params.get("order_by", self.DEFAULT_ORDER_KEY)
        order_func = self.get_aggregate_func(order_by, is_model_comic, autoquery_pk)
        queryset = queryset.annotate(order_value=order_func)

        ########################
        # Annotate name fields #
        ########################
        # Optimized to only lookup what is used on the frontend
        publisher_name = self._NONE_CHARFIELD
        series_name = self._NONE_CHARFIELD
        volume_name = self._NONE_CHARFIELD

        if is_model_comic:
            series_name = F("series__name")
            volume_name = F("volume__name")
        elif model == Volume:
            series_name = F("series__name")
        elif model == Imprint:
            publisher_name = F("publisher__name")

        queryset = queryset.annotate(
            publisher_name=publisher_name,
            series_name=series_name,
            volume_name=volume_name,
        )
        if is_model_comic:
            issue = F("issue")
        else:
            issue = Value(None, IntegerField())
        queryset = queryset.annotate(
            **{f"{UNIONFIX_PREFIX}issue": issue},
        )
        if model not in (Folder, Comic):
            path = self._NONE_CHARFIELD
            queryset = queryset.annotate(
                path=path,
            )

        return queryset

    def _get_model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        if self.kwargs["group"] == "f":
            return "f"
        if (
            self.valid_nav_group_index == len(self.valid_nav_groups) - 1
            or self.valid_nav_group_index is None
        ):
            # special case for lowest valid group
            return "c"
        next_valid_nav_group = self.valid_nav_groups[self.valid_nav_group_index + 1]
        return next_valid_nav_group

    def _set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs["group"]
        self.group_class = self.GROUP_MODEL_MAP[group]

        model_group = self._get_model_group()
        self.model = self.GROUP_MODEL_MAP[model_group]

    def get_folder_queryset(self, object_filter, autoquery_pk):
        """Create folder queryset."""
        # Create the main queries with filters
        folder_list = Folder.objects.filter(object_filter)
        comic_object_filter, _ = self.get_query_filters(True, False)
        comic_list = Comic.objects.filter(comic_object_filter)

        # add annotations for display and sorting
        # and the comic_cover which uses a sort
        folder_list = self._add_annotations(folder_list, Folder, autoquery_pk)
        comic_list = self._add_annotations(comic_list, Comic, autoquery_pk)

        # Reduce to values to make union align columns correctly
        folder_list = folder_list.values(*self._BROWSER_CARD_FIELDS)
        comic_list = comic_list.values(*self._BROWSER_CARD_FIELDS)

        obj_list = folder_list.union(comic_list)
        return obj_list

    def _get_browser_group_queryset(self, object_filter, autoquery_pk):
        """Create and browse queryset."""
        if not self.model:
            raise ValueError("No model set in browser")

        obj_list = self.model.objects.filter(object_filter)
        # obj_list filtering done

        # Add annotations for display and sorting
        obj_list = self._add_annotations(obj_list, self.model, autoquery_pk)

        # Convert to a dict because otherwise the folder/comic union blows
        # up the paginator
        obj_list = obj_list.values(*self._BROWSER_CARD_FIELDS)

        return obj_list

    def _get_folder_up_route(self):
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

    def _set_group_instance(self):
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
                select_related = self._GROUP_INSTANCE_SELECT_RELATED[self.group_class]
                self.group_instance = self.group_class.objects.select_related(
                    *select_related
                ).get(pk=pk)
            except self.group_class.DoesNotExist:
                self._raise_redirect({"group": group}, f"{group}={pk} does not exist!")

    def _get_browse_up_route(self):
        """Get the up route from the first valid ancestor."""
        # Ancestor group
        ancestor_group = None
        if self.valid_nav_group_index is not None and self.valid_nav_group_index > 0:
            ancestor_group = self.valid_nav_groups[self.valid_nav_group_index - 1]

        up_group = ancestor_group
        up_pk = None

        # Ancestor pk
        pk = self.kwargs.get("pk")
        if up_group == "r" or pk == 0:
            up_pk = 0
        elif up_group:
            # get the ancestor pk from the current group
            up_relation = self.GROUP_RELATION[up_group]
            up_pk = getattr(self.group_instance, up_relation).pk

        return up_group, up_pk

    def _get_browser_page_title(self):
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
            if self.group_class == Imprint:
                parent_name = self.group_instance.publisher.name  # type: ignore
            elif self.group_class == Volume:
                parent_name = self.group_instance.series.name  # type: ignore
                group_count = self.group_instance.series.volume_count  # type: ignore
            elif self.group_class == Comic:
                group_count = self.group_instance.volume.issue_count  # type: ignore
            elif self.group_class == Folder:
                folder_path = self.group_instance.path
                if folder_path:
                    parent_name = folder_path
                    prefix = self.group_instance.library.path
                    if prefix[-1] != "/":
                        prefix += "/"
                    if (
                        not self.request.user
                        or not self.request.user.is_staff  # type: ignore
                    ):
                        # remove library path for not admins
                        parent_name = parent_name.removeprefix(prefix)
                    suffix = "/" + self.group_instance.name
                    parent_name = parent_name.removesuffix(suffix)

            group_name = self.group_instance.name

        browser_page_title = {
            "parentName": parent_name,
            "groupName": group_name,
            "groupCount": group_count,
        }

        return browser_page_title

    def _get_valid_top_groups(self):
        """
        Get valid top groups for the current settings.

        Valid top groups are determined by the Browser Settings.
        """
        valid_top_groups = []

        for nav_group in self._NAV_GROUPS:
            if self.params["show"].get(nav_group):
                valid_top_groups.append(nav_group)
        # Issues is always a valid top group
        valid_top_groups += ["c"]

        return valid_top_groups

    def _set_valid_nav_groups(self, valid_top_groups):
        """
        Get valid nav gorups for the current settings.

        Valid nav groups are the top group and below that are also
        enabled in browser settings.

        May always navigate to root 'r' nav group.
        """
        top_group = self.params["top_group"]
        nav_group = self.kwargs["group"]
        self.valid_nav_group_index = None
        possible_nav_groups = valid_top_groups

        for possible_index, possible_nav_group in enumerate(possible_nav_groups):
            if top_group in (possible_nav_group, "c"):
                if top_group == "c":
                    tail_top_groups = []
                else:
                    # all the nav groups past this point, but not 'c' the last one
                    tail_top_groups = possible_nav_groups[possible_index:-1]
                self.valid_nav_groups = ["r"] + tail_top_groups
                for valid_index, valid_nav_group in enumerate(self.valid_nav_groups):
                    if nav_group == valid_nav_group:
                        self.valid_nav_group_index = valid_index
                break

    def _raise_redirect(self, route_changes, reason):
        """Redirect the client to a valid group url."""
        route = deepcopy(self._DEFAULT_ROUTE)
        route["params"].update(route_changes)
        settings = self._get_serializer_settings()
        detail = {"route": route, "settings": settings, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def _validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        try:
            flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW)
            enable_folder_view = flag.on
        except AdminFlag.DoesNotExist:
            enable_folder_view = False
        if not enable_folder_view:
            new_top_group = "r"
            self.params["top_group"] = new_top_group
            self.save_session(self.params)
            reason = "folder view disabled"
            route_changes = {"group": new_top_group}
            self._raise_redirect(route_changes, reason)

        # Validate folder nav group
        # Redirect if nav group is wrong
        group = self.kwargs["group"]
        if group != "f":
            route_changes = {"group": "f"}
            reason = f"{group=} does not match top_group 'f'"
            self._raise_redirect(route_changes, reason)
        self.valid_nav_groups = ["f"]
        self.valid_nav_group_index = 0

    def _validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        top_group = self.params.get("top_group")
        nav_group = self.kwargs["group"]

        # Validate Browser top group
        # Change top_group if its not in the valid top groups
        valid_top_groups = self._get_valid_top_groups()
        if top_group not in valid_top_groups:
            reason = f"top group not in valid nav groups, changed {top_group}"
            if nav_group in valid_top_groups:
                valid_top_group = nav_group
                reason += f"to nav group: {nav_group}"
            else:
                valid_top_group = valid_top_groups[0]
                reason += f"to first valid top group {valid_top_groups[0]}"
            self.params["top_group"] = valid_top_group
            LOG.verbose(reason)  # type: ignore
            self.top_group_changed = True

        # Validate Browser Nav Group
        # Redirect if nav group is wrong
        self._set_valid_nav_groups(valid_top_groups)
        if self.valid_nav_group_index is None:
            self.save_session(self.params)
            new_nav_group = self.valid_nav_groups[0]
            route_changes = {"group": new_nav_group}
            reason = f"Nav group {nav_group} unavailable, redirect to {new_nav_group}"
            self._raise_redirect(route_changes, reason)
        pk = self.kwargs["pk"]
        if nav_group == "r" and pk:
            # r never has a pk
            reason = f"Redirect r with {pk=} to pk 0"
            self._raise_redirect({}, reason)
        lowest_group = self.valid_nav_groups[-1]
        if (
            self.autoquery_first or (self.top_group_changed and nav_group == "r")
        ) and nav_group != lowest_group:
            # if not at the lowest issues showing nav group and its the first aq
            # or the top group changed away from root.
            route_changes = {"group": lowest_group}
            if self.autoquery_first:
                # params change handled in _apply_put, maybe doesn't need redirect.
                reason = "first autoquery: show issues view"
            else:
                reason = f"changed top group so group {lowest_group} shows issues now"
            self.save_session(self.params)
            self._raise_redirect(route_changes, reason)

    def _validate_settings(self):
        """Validate group and top group settings."""
        group = self.kwargs.get("group")
        top_group = self.params.get("top_group")
        if top_group == self.FOLDER_GROUP:
            self._validate_folder_settings()
        else:
            self._validate_browser_group_settings()
        # save route once validated.
        pk = self.kwargs.get("pk")
        page = self.kwargs.get("page")
        # to save last browser route
        self.params["route"] = {"group": group, "pk": pk, "page": page}

    def _apply_put_settings(self, data):
        """Validate submitted settings."""
        serializer = BrowserSettingsSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            LOG.error(serializer.errors)
            LOG.exception(exc)
            raise exc

        self.params = self.get_session()
        for key, value in serializer.validated_data.items():
            snake_key = self._BROWSER_SETTINGS_KEYS_CAMEL_SNAKE_MAP[key]
            if snake_key == "autoquery" and not self.params.get(snake_key) and value:
                self.autoquery_first = True
            if snake_key == "top_group" and self.params.get(snake_key) != value:
                self.top_group_changed = True
            self.params[snake_key] = value
        if self.autoquery_first:
            self.params["order_by"] = "search_score"
            self.params["order_reverse"] = True

    def _page_out_out_bounds(self, page, num_pages):
        """Redirect page out of bounds."""
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk", 1)
        route = {"group": group, "pk": pk}
        reason = f"{page=} does not exist!"
        if page < 1:
            route["page"] = 1
        elif page > num_pages:
            route["page"] = num_pages
        LOG.verbose(f"{reason} redirect to {route}.")  # type: ignore
        self._raise_redirect(route, reason)

    def _paginate(self, queryset):
        """Paginate the queryset into a final object list."""
        paginator = Paginator(queryset, self._MAX_OBJ_PER_PAGE, orphans=self._ORPHANS)
        page = self.kwargs.get("page", 1)
        try:
            obj_list = paginator.page(page).object_list
            covers = True
        except EmptyPage:
            if page < 1 or page > paginator.num_pages:
                self._page_out_out_bounds(page, paginator.num_pages)
            LOG.warning(f"No items on page {page}")
            obj_list = self.model.objects.filter(pk=-1)  # paginator.page(1).object_list
            covers = False
        return obj_list, paginator.num_pages, covers

    def _get_browser_page(self):
        """Validate settings and get the querysets."""
        self._validate_settings()
        self._set_browse_model()
        # Create the main query with the filters
        try:
            object_filter, autoquery_pk = self.get_query_filters(
                self.model == Comic, False
            )
        except Folder.DoesNotExist:
            pk = self.kwargs.get("pk")
            self._raise_redirect(
                {"group": "f"}, f"folder {pk} Does not exist! Redirect to root folder."
            )
        group = self.kwargs.get("group")

        if group == self.FOLDER_GROUP:
            queryset = self.get_folder_queryset(object_filter, autoquery_pk)
        else:
            queryset = self._get_browser_group_queryset(object_filter, autoquery_pk)

        # Order
        order_by, order_keys = self.get_order_by(self.model)
        queryset = queryset.order_by(*order_by)

        # Pagination
        obj_list, num_pages, covers = self._paginate(queryset)

        # Ensure comic covers exist for all browser cards
        if group == self.FOLDER_GROUP or not covers:
            # trimming the union query further breaks alignment
            comic_cover_tuple = obj_list
        else:
            comic_cover_tuple = obj_list.values(
                "path", f"{UNIONFIX_PREFIX}cover_path", *order_keys
            )
        task = BulkComicCoverCreateTask(False, comic_cover_tuple)  # type: ignore
        LIBRARIAN_QUEUE.put_nowait(task)

        # Save the session
        self.save_session(self.params)

        # get additional context
        self._set_group_instance()
        if group == self.FOLDER_GROUP:
            up_group, up_pk = self._get_folder_up_route()
        else:
            up_group, up_pk = self._get_browse_up_route()
        browser_page_title = self._get_browser_page_title()

        if up_group is not None and up_pk is not None:
            up_route = {"group": up_group, "pk": up_pk, "page": 1}
        else:
            up_route = {}

        efv_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW)

        libraries_exist = Library.objects.exists()

        queries = SearchQuery.objects.order_by("-used_at").values_list(
            "text", flat=True
        )[: BrowserPageSerializer.NUM_AUTOCOMPLETE_QUERIES]

        # construct final data structure
        browser_page = {
            "upRoute": up_route,
            "browserTitle": browser_page_title,
            "modelGroup": self.model_group,
            "objList": obj_list,
            "numPages": num_pages,
            "formChoices": {"enableFolderView": efv_flag.on},
            "librariesExist": libraries_exist,
            "queries": queries,
        }
        return browser_page

    def _load_params(self, from_request=False):
        """Load self.params from the session, update with request."""
        self.top_group_changed = False
        self.autoquery_first = False
        if from_request:
            self._apply_put_settings(self.request.data)
        else:
            self.params = self.get_session()

    def put(self, request, *args, **kwargs):
        """Create the view."""
        self._load_params(from_request=True)
        browser_page = self._get_browser_page()

        serializer = BrowserPageSerializer(browser_page)
        return Response(serializer.data)

    def _get_serializer_settings(self):
        """Get the camelcase settings."""
        settings = {}
        for key in self._BROWSER_SETTINGS_KEYS_SNAKE_CAMEL_MAP:
            camel_key = camelcase(key)
            settings[camel_key] = self.params.get(key)
        return settings

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self._load_params()
        browser_page = self._get_browser_page()

        settings = self._get_serializer_settings()
        latest_version = get_latest_version(PACKAGE_NAME)

        data = {
            "settings": settings,
            "browserPage": browser_page,
            "versions": {"installed": VERSION, "latest": latest_version},
        }
        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
