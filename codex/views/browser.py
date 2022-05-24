"""Views for browsing comic library."""
from copy import deepcopy
from typing import Optional, Union

from django.core.paginator import EmptyPage, Paginator
from django.db.models import (
    BooleanField,
    CharField,
    DecimalField,
    F,
    IntegerField,
    Max,
    Value,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.exceptions import SeeOtherRedirectError
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
    BrowserCardSerializer,
    BrowserOpenedSerializer,
    BrowserPageSerializer,
    BrowserSettingsSerializer,
)
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.settings.logging import get_logger
from codex.version import PACKAGE_NAME, VERSION, get_latest_version
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBaseView


LOG = get_logger(__name__)


class BrowserView(BrowserMetadataBaseView):
    """Browse comics with a variety of filters and sorts."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    _MODEL_GROUP_MAP = {
        v: k for k, v in BrowserMetadataBaseView.GROUP_MODEL_MAP.items()
    }
    _NAV_GROUPS = "rpisv"
    _MAX_OBJ_PER_PAGE = 100
    _ORPHANS = int(_MAX_OBJ_PER_PAGE / 20)
    # TODO move to BrowserCardSerializer?
    # TODO doesn't need snakecase
    _BROWSER_CARD_ORDERED_UNIONFIX_VALUES_MAP = dict(
        (
            (UNIONFIX_PREFIX + field, F(field))
            for field in sorted(BrowserCardSerializer().get_fields())
        )
    )
    _NONE_DECIMALFIELD = Value(None, DecimalField())
    _EMPTY_CHARFIELD = Value("", CharField())
    _ZERO_INTEGERFIELD = Value(0, IntegerField())
    _NONE_BOOLFIELD = Value(None, BooleanField())

    _GROUP_INSTANCE_SELECT_RELATED = {
        Comic: ("series", "volume"),
        Volume: ("series",),
        Series: (None,),
        Imprint: ("publisher",),
        Publisher: (None,),
        Folder: ("parent_folder",),
    }
    _DEFAULT_ROUTE = {
        "name": "browser",
        "params": BrowserMetadataBaseView.SESSION_DEFAULTS[
            BrowserMetadataBaseView.BROWSER_KEY
        ]["route"],
    }
    _GROUP_INDEX_MAP = {
        "p": 0,
        "i": 1,
        "s": 2,
        "v": 3,
        "c": 4,
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
            queryset = queryset.annotate(library=self._ZERO_INTEGERFIELD)

        #######################
        # Sortable aggregates #
        #######################
        order_key = self.get_order_key()
        order_func = self.get_aggregate_func(order_key, model, autoquery_pk)
        queryset = queryset.annotate(order_value=order_func)

        ########################
        # Annotate name fields #
        ########################
        # Optimized to only lookup what is used on the frontend
        publisher_name = self.NONE_CHARFIELD
        series_name = self.NONE_CHARFIELD
        volume_name = self.NONE_CHARFIELD

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
        if not is_model_comic:
            queryset = queryset.annotate(
                issue=self._NONE_DECIMALFIELD,
                issue_suffix=self._EMPTY_CHARFIELD,
            )
        if model not in (Folder, Comic):
            queryset = queryset.annotate(path=self.NONE_CHARFIELD)

        if not is_model_comic:
            queryset = queryset.annotate(read_ltr=self._NONE_BOOLFIELD)

        return queryset

    def _get_model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        if self.kwargs["group"] == self.FOLDER_GROUP:
            return self.FOLDER_GROUP
        if (
            self.valid_nav_group_index == len(self.valid_nav_groups) - 1
            or self.valid_nav_group_index is None
        ):
            # special case for lowest valid group
            return self.COMIC_GROUP
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

        # Create ordered annotated values to make union align columns correctly because
        # django lacks a way to specify values column order.
        folder_list = folder_list.values(
            **self._BROWSER_CARD_ORDERED_UNIONFIX_VALUES_MAP
        )
        comic_list = comic_list.values(**self._BROWSER_CARD_ORDERED_UNIONFIX_VALUES_MAP)

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
        # up the paginator. Use the same annotations for the serializer.
        obj_list = obj_list.values(**self._BROWSER_CARD_ORDERED_UNIONFIX_VALUES_MAP)

        return obj_list

    def _get_folder_up_route(self):
        """Get out parent's pk."""
        up_group = self.FOLDER_GROUP
        up_pk = None

        # Recall root id & relative path from way back in
        # object creation
        if self.group_instance and isinstance(self.group_instance, Folder):
            if self.group_instance.parent_folder:
                up_pk = self.group_instance.parent_folder.pk
            else:
                up_pk = 0

        return up_group, up_pk

    def _set_group_instance(self):
        """Create group_class instance."""
        pk = self.kwargs.get("pk")
        self.group_instance: Optional[
            Union[Folder, Publisher, Imprint, Series, Volume]
        ] = None
        if not pk:
            return
        try:
            select_related = self._GROUP_INSTANCE_SELECT_RELATED[self.group_class]
            self.group_instance = self.group_class.objects.select_related(
                *select_related
            ).get(pk=pk)
        except self.group_class.DoesNotExist:
            group = self.kwargs.get("group")
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
            if isinstance(self.group_instance, Imprint):
                parent_name = self.group_instance.publisher.name
            elif isinstance(self.group_instance, Volume):
                parent_name = self.group_instance.series.name
                group_count = self.group_instance.series.volume_count
            elif isinstance(self.group_instance, Comic):
                group_count = self.group_instance.volume.issue_count
            elif isinstance(self.group_instance, Folder):
                folder_path = self.group_instance.path
                if folder_path:
                    parent_name = folder_path
                    prefix = self.group_instance.library.path
                    if prefix[-1] != "/":
                        prefix += "/"
                    if not self.is_admin():
                        # remove library path for not admins
                        parent_name = parent_name.removeprefix(prefix)
                    suffix = "/" + self.group_instance.name
                    parent_name = parent_name.removesuffix(suffix)

            group_name = self.group_instance.name

        browser_page_title = {
            "parent_name": parent_name,
            "group_name": group_name,
            "group_count": group_count,
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
        valid_top_groups += [self.COMIC_GROUP]

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
            if top_group in (possible_nav_group, self.COMIC_GROUP):
                if top_group == self.COMIC_GROUP:
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
        detail = {"route": route, "settings": self.params, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def _validate_folder_settings(self, enable_folder_view):
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        if not enable_folder_view:
            new_top_group = "r"
            self.params["top_group"] = new_top_group
            self.save_params_to_session()
            reason = "folder view disabled"
            route_changes = {"group": new_top_group}
            self._raise_redirect(route_changes, reason)

        self.params["top_group"] = self.FOLDER_GROUP
        self.valid_nav_groups = [self.FOLDER_GROUP]
        self.valid_nav_group_index = 0

    def _validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        nav_group = self.kwargs["group"]
        top_group = self.params.get("top_group")

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
            LOG.verbose(reason)
            self.top_group_changed = True

        # Validate Browser Nav Group
        # Redirect if nav group is wrong
        self._set_valid_nav_groups(valid_top_groups)
        if self.valid_nav_group_index is None:
            self.save_params_to_session()
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
            self.top_group_changed
            and nav_group == "r"
            and lowest_group != "r"
            and self._GROUP_INDEX_MAP[self.old_top_group]
            > self._GROUP_INDEX_MAP[top_group]
        ):
            # if the top group changed and we're at the root and the new top group is
            # lower than change to the proper nav group.
            nav_group_from_old_top_group = lowest_group
            for group in self.valid_nav_groups:
                if group == self.old_top_group:
                    break
                nav_group_from_old_top_group = group
                # keep the top group the same
            route_changes = {"group": nav_group_from_old_top_group}
            reason = f"changed top group: {nav_group_from_old_top_group} replaces root"
            self.save_params_to_session()
            self._raise_redirect(route_changes, reason)
        if self.autoquery_first:
            route_changes = {"group": lowest_group}
            # params change handled in _apply_put, maybe doesn't need redirect.
            reason = "first autoquery: show issues view"
            self.save_params_to_session()
            self._raise_redirect(route_changes, reason)

    def _validate_settings(self):
        """Validate group and top group settings."""
        group = self.kwargs.get("group")
        order_key = self.get_order_key()
        enable_folder_view = False
        if group == self.FOLDER_GROUP or order_key == "path":
            try:
                enable_folder_view = (
                    AdminFlag.objects.only("on")
                    .get(name=AdminFlag.ENABLE_FOLDER_VIEW)
                    .on
                )
            except Exception:
                pass

        if group == self.FOLDER_GROUP:
            self._validate_folder_settings(enable_folder_view)
        else:
            self._validate_browser_group_settings()

        if order_key == "path" and not enable_folder_view:
            self.params["order_by"] = "sort_name"
            LOG.warning("order by path not allowed by admin flag.")

        # save route once validated.
        pk = self.kwargs.get("pk")
        page = self.kwargs.get("page")
        # to save last browser route
        self.params["route"] = {"group": group, "pk": pk, "page": page}

    def _apply_put_settings(self, data):
        """Validate submitted settings and apply them over the session settings."""
        serializer = BrowserSettingsSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            LOG.error(serializer.errors)
            LOG.exception(exc)
            raise exc

        for key, value in serializer.validated_data.items():
            if key == "autoquery" and not self.params.get(key) and value:
                self.autoquery_first = True
            elif key == "top_group" and self.params.get(key) != value:
                self.top_group_changed = True
                self.old_top_group = self.params.get(key)
            self.params[key] = value
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
        LOG.verbose(f"{reason} redirect to {route}.")
        self._raise_redirect(route, reason)

    def _paginate(self, queryset):
        """Paginate the queryset into a final object list."""
        paginator = Paginator(queryset, self._MAX_OBJ_PER_PAGE, orphans=self._ORPHANS)
        page = self.kwargs.get("page", 1)
        try:
            obj_list = paginator.page(page).object_list
        except EmptyPage:
            if page < 1 or page > paginator.num_pages:
                self._page_out_out_bounds(page, paginator.num_pages)
            LOG.warning(f"No items on page {page}")
            obj_list = self.model.objects.filter(pk=-1)  # paginator.page(1).object_list
        return obj_list, paginator.num_pages

    def _get_browser_page(self):
        """Validate settings and get the querysets."""
        self._validate_settings()
        self._set_browse_model()
        # Create the main query with the filters
        is_model_comic = self.model == Comic
        try:
            object_filter, autoquery_pk = self.get_query_filters(is_model_comic, False)
        except Folder.DoesNotExist:
            pk = self.kwargs.get("pk")
            self._raise_redirect(
                {"group": self.FOLDER_GROUP},
                f"folder {pk} Does not exist! Redirect to root folder.",
            )
        group = self.kwargs.get("group")

        if group == self.FOLDER_GROUP:
            queryset = self.get_folder_queryset(object_filter, autoquery_pk)
        else:
            queryset = self._get_browser_group_queryset(object_filter, autoquery_pk)

        # Order
        order_by = self.get_order_by(self.model)
        queryset = queryset.order_by(*order_by)

        # Paginate
        obj_list, num_pages = self._paginate(queryset)

        # Save the session
        self.save_params_to_session()

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

        if is_model_comic:
            # runs obj list query twice :/
            issue_max = obj_list.aggregate(Max("issue"))["issue__max"]
        else:
            issue_max = 0

        # construct final data structure
        browser_page = {
            "up_route": up_route,
            "browser_title": browser_page_title,
            "model_group": self.model_group,
            "obj_list": obj_list,
            "issue_max": issue_max,
            "num_pages": num_pages,
            "admin_flags": {"enable_folder_view": efv_flag.on},
            "libraries_exist": libraries_exist,
            "queries": queries,
        }
        return browser_page

    def _load_params(self, from_request=False):
        """Load self.params from the session, update with request."""
        self.top_group_changed = False
        self.autoquery_first = False
        self.load_params_from_session()
        if from_request:
            self._apply_put_settings(self.request.data)

    def put(self, request, *args, **kwargs):
        """Create the view."""
        self._load_params(from_request=True)
        browser_page = self._get_browser_page()

        serializer = BrowserPageSerializer(browser_page)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self._load_params()
        browser_page = self._get_browser_page()
        latest_version = get_latest_version(PACKAGE_NAME)

        data = {
            "settings": self.params,
            "browser_page": browser_page,
            "versions": {"installed": VERSION, "latest": latest_version},
        }
        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
