"""Views for browsing comic library."""

from copy import deepcopy
from types import MappingProxyType
from typing import ClassVar

from django.core.paginator import EmptyPage, Paginator
from django.db.models import F, Max, Value
from django.db.models.fields import (
    CharField,
)
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.exceptions import SeeOtherRedirectError
from codex.logger.logging import get_logger
from codex.models import (
    AdminFlag,
    BrowserGroupModel,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    StoryArc,
    Timestamp,
    Volume,
)
from codex.serializers.browser.page import BrowserPageSerializer
from codex.serializers.choices import CHOICES, DEFAULTS
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.browser_annotations import BrowserAnnotationsView

LOG = get_logger(__name__)


class BrowserView(BrowserAnnotationsView):
    """Browse comics with a variety of filters and sorts."""

    permission_classes: ClassVar[list] = [IsAuthenticatedOrEnabledNonUsers]  # type: ignore
    serializer_class = BrowserPageSerializer

    MAX_OBJ_PER_PAGE = 100
    _MODEL_GROUP_MAP = MappingProxyType(
        {v: k for k, v in BrowserAnnotationsView.GROUP_MODEL_MAP.items()}
    )
    _NAV_GROUPS = "rpisv"
    _ORPHANS = int(MAX_OBJ_PER_PAGE / 20)

    _GROUP_INSTANCE_SELECT_RELATED = MappingProxyType(
        {
            Comic: ("series", "volume"),
            Volume: ("series",),
            Series: (None,),
            Imprint: ("publisher",),
            Publisher: (None,),
            Folder: ("parent_folder",),
            StoryArc: (None,),
        }
    )
    DEFAULT_ROUTE_NAME = "browser"
    _DEFAULT_ROUTE = MappingProxyType(
        {
            "name": DEFAULT_ROUTE_NAME,
            "params": deepcopy(DEFAULTS["route"]),
        }
    )
    _OPDS_M2M_RELS = (
        "characters",
        "genres",
        "locations",
        "series_groups",
        "story_arc_numbers",
        "story_arc_numbers__story_arc",
        "tags",
        "teams",
        "contributors",
        "contributors__role",
        "contributors__person",
    )

    is_opds_2_acquisition = False

    def _annotate_group_names(self, queryset, model):
        """Annotate name fields."""
        # Optimized to only lookup what is used on the frontend
        group_names = {}
        if model == Comic:
            group_names = {
                "publisher_name": F("publisher__name"),
                "series_name": F("series__name"),
                "volume_name": F("volume__name"),
            }
            if self.is_opds_2_acquisition:
                group_names["imprint_name"] = F("imprint__name")
        elif model == Volume:
            group_names["series_name"] = F("series__name")
        elif model == Imprint:
            group_names["publisher_name"] = F("publisher__name")
        return queryset.annotate(**group_names)

    def _add_annotations(self, queryset, model, search_scores: dict):
        """Annotations for display and sorting."""
        queryset = self.annotate_common_aggregates(queryset, model, search_scores)

        # Annotate Group
        self.model_group = self._MODEL_GROUP_MAP[model]
        queryset = queryset.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )
        # Hoist Group Names
        return self._annotate_group_names(queryset, model)

    def _get_model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        group = self.kwargs["group"]
        if group == self.FOLDER_GROUP:
            return group
        if group == self.STORY_ARC_GROUP:
            pk = self.kwargs["pk"]
            return self.COMIC_GROUP if pk else group
        if group == self.valid_nav_groups[-1]:
            # special case for lowest valid group
            return self.COMIC_GROUP
        return self.valid_nav_groups[self.valid_nav_groups.index(group) + 1]

    def _set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs["group"]
        self.group_class = self.GROUP_MODEL_MAP[group]

        model_group = self._get_model_group()
        self.model = self.GROUP_MODEL_MAP[model_group]

    def _get_group_queryset(self, search_scores: dict):
        """Create group queryset."""
        if not self.model:
            reason = "Model not set in browser."
            raise ValueError(reason)
        if self.model != Comic:
            object_filter = self.get_query_filters(self.model, search_scores, False)
            qs = self.model.objects.filter(object_filter)
            qs = self._add_annotations(qs, self.model, search_scores)
            qs = self.add_order_by(qs, self.model)
        else:
            qs = self.model.objects.none()
        return qs

    def _get_book_queryset(self, search_scores: dict):
        """Create book queryset."""
        if self.model in (Comic, Folder):
            object_filter = self.get_query_filters(Comic, search_scores, False)
            qs = Comic.objects.filter(object_filter)
            qs = self._add_annotations(qs, Comic, search_scores)
            qs = self.add_order_by(qs, Comic)
            if limit := self.params.get("limit"):
                qs = qs[:limit]
        else:
            qs = Comic.objects.none()
        return qs

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

    def _get_story_arc_up_route(self):
        """Get one level hierarchy."""
        up_group = self.STORY_ARC_GROUP
        up_group = 0 if self.group_instance else None
        return self.STORY_ARC_GROUP, up_group

    def _set_group_instance(self):
        """Create group_class instance."""
        pk = self.kwargs.get("pk")
        if pk and self.group_class:
            try:
                select_related: tuple[str, ...] = self._GROUP_INSTANCE_SELECT_RELATED[
                    self.group_class
                ]  # type: ignore
                self.group_instance: BrowserGroupModel | None = (
                    self.group_class.objects.select_related(*select_related).get(pk=pk)
                )
            except self.group_class.DoesNotExist:
                group = self.kwargs.get("group")
                reason = f"{group}={pk} does not exist!"
                self._raise_redirect({"group": group, "pk": 0, "page": 1}, reason)
        else:
            self.group_instance: BrowserGroupModel | None = None

    def _get_browse_up_route(self):
        """Get the up route from the first valid ancestor."""
        # Ancestor group
        group = self.kwargs.get("group")
        if self.valid_nav_groups.index(group) > 0:
            ancestor_group = self.valid_nav_groups[
                self.valid_nav_groups.index(group) - 1
            ]
        else:
            ancestor_group = None

        up_group = ancestor_group
        up_pk = None

        # Ancestor pk
        pk = self.kwargs.get("pk")
        if up_group == self.ROOT_GROUP or pk == 0:
            up_pk = 0
        elif up_group:
            # get the ancestor pk from the current group
            up_relation = self.GROUP_RELATION[up_group]
            up_pk = getattr(self.group_instance, up_relation).pk

        return up_group, up_pk

    def _get_root_group_name(self):
        if not self.model:
            reason = "No model set in browser"
            raise ValueError(reason)
        plural = self.model._meta.verbose_name_plural
        if not plural:
            reason = f"No plural name for {self.model}"
            raise ValueError(reason)
        return plural.capitalize()

    def _get_folder_parent_name(self):
        """Get title for a folder browser page."""
        group_instance: Folder = self.group_instance  # type: ignore
        folder_path = group_instance.path
        if not folder_path:
            return ""

        parent_name = folder_path
        prefix = group_instance.library.path
        if prefix[-1] != "/":
            prefix += "/"
        if not self.is_admin():
            # remove library path for not admins
            parent_name = parent_name.removeprefix(prefix)
        suffix = "/" + group_instance.name
        return parent_name.removesuffix(suffix)

    def _get_browser_page_title(self):
        """Get the proper title for this browse level."""
        pk = self.kwargs.get("pk")
        parent_name = ""
        group_count = 0
        group_name = ""
        if pk == 0:
            group_name = self._get_root_group_name()
        elif self.group_instance:
            if isinstance(self.group_instance, Imprint):
                parent_name = self.group_instance.publisher.name
            elif isinstance(self.group_instance, Volume):
                parent_name = self.group_instance.series.name
                group_count = self.group_instance.series.volume_count
            elif isinstance(self.group_instance, Comic):
                group_count = self.group_instance.volume.issue_count
            elif isinstance(self.group_instance, Folder):
                parent_name = self._get_folder_parent_name()
            group_name = self.group_instance.name

        return {
            "parent_name": parent_name,
            "group_name": group_name,
            "group_count": group_count,
        }

    def _page_out_out_bounds(self, page, num_pages):
        """Redirect page out of bounds."""
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk", 1)
        new_page = num_pages if page > num_pages else 1
        route_changes = {"group": group, "pk": pk, "page": new_page}
        reason = f"{page=} does not exist!"
        LOG.debug(f"{reason} redirect to page {new_page}.")
        self._raise_redirect(route_changes, reason)

    def _paginate_section(self, qs, max_obj_per_page, page_counts):
        """Paginate a group or Comic section."""
        num_pages, total_count, model = page_counts
        paginator = Paginator(qs, max_obj_per_page, orphans=self._ORPHANS)
        page = self.kwargs.get("page", 1)
        try:
            qs = paginator.page(page).object_list
            num_pages = max(num_pages, paginator.num_pages)
            total_count += paginator.count
        except EmptyPage:
            if page < 1 or page > paginator.num_pages:
                self._page_out_out_bounds(page, paginator.num_pages)
            model_name = self.model.__name__ if self.model else "NO_MODEL"
            LOG.warning(f"No {model_name}s on page {page}")
            model.objects.none()

        return qs, num_pages, total_count

    def _paginate(self, group_qs, book_qs):
        """Paginate the queryset into a final object list."""
        num_pages = 0
        total_count = 0

        if group_qs.count():
            page_counts = (num_pages, total_count, self.model)
            group_qs, num_pages, total_count = self._paginate_section(
                group_qs, self.MAX_OBJ_PER_PAGE, page_counts
            )

        if book_qs.count():
            book_max_obj_per_page = max(0, self.MAX_OBJ_PER_PAGE - group_qs.count())
            page_counts = (num_pages, total_count, Comic)
            group_qs, num_pages, total_count = self._paginate_section(
                group_qs, book_max_obj_per_page, page_counts
            )

        return group_qs, book_qs, num_pages, total_count

    def get_object(self):
        """Validate settings and get the querysets."""
        self._set_browse_model()
        self.set_rel_prefix(self.model)
        self._set_group_instance()  # Placed up here to invalidate earlier
        # Create the main query with the filters
        search_scores: dict = self.get_search_scores()
        group = self.kwargs.get("group")

        group_qs = self._get_group_queryset(search_scores)
        book_qs = self._get_book_queryset(search_scores)

        # Paginate
        group_qs, book_qs, num_pages, total_count = self._paginate(group_qs, book_qs)

        # get additional context
        if group == self.FOLDER_GROUP:
            up_group, up_pk = self._get_folder_up_route()
        elif group == self.STORY_ARC_GROUP:
            up_group, up_pk = self._get_story_arc_up_route()
        else:
            up_group, up_pk = self._get_browse_up_route()
        browser_page_title = self._get_browser_page_title()

        if up_group is not None and up_pk is not None:
            up_route = {"group": up_group, "pk": up_pk, "page": 1}
        else:
            up_route = {}

        efv_flag = AdminFlag.objects.only("on").get(
            key=AdminFlag.FlagChoices.FOLDER_VIEW.value
        )

        libraries_exist = Library.objects.exists()

        # runs obj list query twice :/
        issue_number_max = book_qs.only("issue_number").aggregate(Max("issue_number"))[
            "issue_number__max"
        ]

        covers_timestamp = int(
            Timestamp.objects.get(
                key=Timestamp.TimestampChoices.COVERS.value
            ).updated_at.timestamp()
        )

        # construct final data structure
        return MappingProxyType(
            {
                "up_route": up_route,
                "browser_title": browser_page_title,
                "model_group": self.model_group,
                "groups": group_qs,
                "books": book_qs,
                "issue_number_max": issue_number_max,
                "num_pages": num_pages,
                "total_count": total_count,
                "admin_flags": {"folder_view": efv_flag.on},
                "libraries_exist": libraries_exist,
                "covers_timestamp": covers_timestamp,
            }
        )

    def _get_valid_top_groups(self):
        """Get valid top groups for the current settings.

        Valid top groups are determined by the Browser Settings.
        """
        valid_top_groups = []

        show: MappingProxyType = self.params["show"]  # type:ignore
        for nav_group in self._NAV_GROUPS:
            if show.get(nav_group):
                valid_top_groups.append(nav_group)
        # Issues is always a valid top group
        valid_top_groups += [self.COMIC_GROUP]

        return valid_top_groups

    def _set_valid_browse_nav_groups(self, valid_top_groups):
        """Get valid nav groups for the current settings.

        Valid nav groups are the top group and below that are also
        enabled in browser settings.

        May always navigate to root 'r' nav group.
        """
        top_group = self.params["top_group"]
        nav_group = self.kwargs["group"]
        self.valid_nav_groups = (self.ROOT_GROUP,)

        for possible_index, possible_nav_group in enumerate(valid_top_groups):
            if top_group == possible_nav_group:
                # all the nav groups past this point,
                # 'c' is obscured by the web reader url, but valid for opds
                tail_top_groups = valid_top_groups[possible_index:]

                self.valid_nav_groups = (*self.valid_nav_groups, *tail_top_groups)
                if nav_group not in self.valid_nav_groups:
                    route_changes = {"group": self.ROOT_GROUP}
                    reason = (
                        f"Nav group {nav_group} unavailable, "
                        f"redirect to {self.ROOT_GROUP}"
                    )
                    self._raise_redirect(route_changes, reason)
                break

    def _raise_redirect(self, route_mask, reason, settings_mask=None):
        """Redirect the client to a valid group url."""
        route = deepcopy(dict(self._DEFAULT_ROUTE))
        route["params"].update(route_mask)  # type: ignore
        settings = deepcopy(self.params)
        if settings_mask:
            settings.update(settings_mask)
        detail = {"route": route, "settings": settings, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def _validate_folder_settings(self, enable_folder_view):
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        if not enable_folder_view:
            reason = "folder view disabled"
            valid_top_groups = self._get_valid_top_groups()
            settings_mask = {"top_group": valid_top_groups[0]}
            self._raise_redirect({}, reason, settings_mask)

        top_group = self.params["top_group"]
        if top_group != self.FOLDER_GROUP:
            self.params["top_group"] = self.FOLDER_GROUP

        # set valid folder nav groups
        self.valid_nav_groups = (self.FOLDER_GROUP,)

    def _validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        nav_group = self.kwargs["group"]
        top_group = self.params.get("top_group")
        pk = self.kwargs["pk"]

        # Validate Browser top_group
        # Change top_group if its not in the valid top groups
        valid_top_groups = self._get_valid_top_groups()
        if top_group not in valid_top_groups:
            reason = f"top_group {top_group} not in valid nav groups, changed to "
            if nav_group in valid_top_groups:
                valid_top_group = nav_group
                reason += "nav group: "
            else:
                valid_top_group = valid_top_groups[0]
                reason += "first valid top group "
            reason += valid_top_group
            LOG.debug(reason)
            page = self.kwargs["page"]
            route = {"group": nav_group, "pk": pk, "page": page}
            settings_mask = {"top_group": valid_top_group}
            self._raise_redirect(route, reason, settings_mask)

        # Validate Browser nav_group
        # Redirect if nav group is wrong
        self._set_valid_browse_nav_groups(valid_top_groups)

        # Validate pk
        if nav_group == self.ROOT_GROUP and pk:
            # r never has a pk
            reason = f"Redirect r with {pk=} to pk 0"
            self._raise_redirect({"pk": 0}, reason)

    def _validate_story_arc_settings(self):
        """Validate story arc settings."""
        top_group = self.params["top_group"]
        if top_group != self.STORY_ARC_GROUP:
            self.params["top_group"] = self.STORY_ARC_GROUP

    def _set_route_param(self):
        """Set the route param."""
        group = self.kwargs.get("group", "r")
        pk = self.kwargs.get("pk", 0)
        page = self.kwargs.get("page", 1)
        self.params["route"] = {"group": group, "pk": pk, "page": page}

    def validate_settings(self):
        """Validate group and top group settings."""
        group = self.kwargs.get("group")
        self.set_order_key()
        enable_folder_view = False
        if group == self.FOLDER_GROUP or self.order_key == "path":
            key = AdminFlag.FlagChoices.FOLDER_VIEW.value
            try:
                enable_folder_view = AdminFlag.objects.only("on").get(key=key).on
            except Exception as err:
                title = CHOICES["admin"]["adminFlags"].get(key)
                LOG.warning(f"Getting {title} AdminFlag: {err}")

        if group == self.FOLDER_GROUP:
            self._validate_folder_settings(enable_folder_view)
        elif group == self.STORY_ARC_GROUP:
            self._validate_story_arc_settings()
        else:
            self._validate_browser_group_settings()

        # Validate path sort
        if self.order_key == "path" and not enable_folder_view:
            pk = self.kwargs("pk")
            page = self.kwargs("page")
            route_changes = {"group": group, "pk": pk, "page": page}
            reason = "order by path not allowed by admin flag."
            settings_mask = {"order_by": "sort_name"}
            self._raise_redirect(route_changes, reason, settings_mask)

    @extend_schema(request=BrowserAnnotationsView.input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Get browser settings."""
        self.parse_params()
        self.validate_settings()
        self._set_route_param()
        data = self.get_object()
        serializer = self.get_serializer(data)
        self.save_params_to_session(self.params)
        return Response(serializer.data)
