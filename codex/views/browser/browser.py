"""Views for browsing comic library."""

from copy import deepcopy
from math import ceil, floor, log10
from os import sep
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Max
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
from codex.serializers.choices import DEFAULTS
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.browser_breadcrumbs import BrowserBreadcrumbsView
from codex.views.browser.const import MAX_OBJ_PER_PAGE

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


LOG = get_logger(__name__)


class BrowserView(BrowserBreadcrumbsView):
    """Browse comics with a variety of filters and sorts."""

    permission_classes: ClassVar[list] = [IsAuthenticatedOrEnabledNonUsers]  # type: ignore
    serializer_class = BrowserPageSerializer

    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
            AdminFlag.FlagChoices.IMPORT_METADATA.value: "import_metadata",
            AdminFlag.FlagChoices.DYNAMIC_GROUP_COVERS.value: "dynamic_group_covers",
        }
    )

    _GROUP_INSTANCE_SELECT_RELATED: MappingProxyType[
        type[BrowserGroupModel], tuple[str | None, ...]
    ] = MappingProxyType(
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
    DEFAULT_ROUTE = MappingProxyType(
        {
            "name": "browser",
            "params": deepcopy(DEFAULTS["breadcrumbs"][0]),
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
    TARGET = "browser"

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.is_opds_2_acquisition = False
        self.group_query: QuerySet = Comic.objects.none()
        self.group_instance: BrowserGroupModel | None = None
        self.valid_nav_groups: tuple[str, ...] = ()

    def _raise_redirect(self, reason, route_mask=None, settings_mask=None):
        """Redirect the client to a valid group url."""
        route = deepcopy(dict(self.DEFAULT_ROUTE))
        if route_mask:
            route["params"].update(route_mask)  # type: ignore
        settings = deepcopy(dict(self.params))
        if settings_mask:
            settings.update(settings_mask)
        detail = {"route": route, "settings": settings, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def get_model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        group = self.kwargs["group"]
        if group == self.FOLDER_GROUP:
            return group
        if group == self.STORY_ARC_GROUP:
            pks = self.kwargs.get("pks")
            return self.COMIC_GROUP if pks else group
        if group == self.valid_nav_groups[-1]:
            # special case for lowest valid group
            return self.COMIC_GROUP
        return self.valid_nav_groups[self.valid_nav_groups.index(group) + 1]

    def _get_common_queryset(self, model):
        """Create queryset common to group & books."""
        object_filter = self.get_query_filters(model, False)
        qs = model.objects.filter(object_filter)
        qs = self.filter_by_annotations(qs, model)
        count_group_by = self.get_group_by(model)
        count = qs.group_by(count_group_by).count()
        if count:
            qs = self.annotate_order_aggregates(qs, model)
            qs = self.add_order_by(qs, model)
            if limit := self.params.get("limit"):
                # limit only is set by some opds views
                qs = qs[:limit]
                count = min(count, limit)  # type: ignore

        return qs, count

    def _get_group_queryset(self):
        """Create group queryset."""
        if not self.model:
            reason = "Model not set for browser queryset."
            raise ValueError(reason)
        elif self.is_model_comic:  # noqa: RET506
            qs = self.model.objects.none()
            count = 0
        else:
            qs, count = self._get_common_queryset(self.model)
            group_by = self.get_group_by()
            qs = qs.group_by(group_by)
        return qs, count

    def _get_book_queryset(self):
        """Create book queryset."""
        if self.model in (Comic, Folder):
            qs, count = self._get_common_queryset(Comic)
        else:
            qs = Comic.objects.none()
            count = 0
        return qs, count

    def _set_group_query_and_instance(self):
        """Create group_class instance."""
        pks = self.kwargs.get("pks")
        if pks and self.group_class:
            try:
                select_related: tuple[str | None, ...] = (
                    self._GROUP_INSTANCE_SELECT_RELATED[self.group_class]
                )
                self.group_query = self.group_class.objects.select_related(
                    *select_related
                ).filter(pk__in=pks)
            except self.group_class.DoesNotExist:
                group = self.kwargs.get("group")
                page = self.kwargs.get("page")
                if group == "r" and not pks and page == 1:
                    self.group_query = self.group_class.objects.none()
                else:
                    reason = f"{group}__in={pks} does not exist!"
                    self._raise_redirect(reason, route_mask={"group": group})
        elif self.group_class:
            self.group_query = self.group_class.objects.none()
        else:
            self.group_query = Comic.objects.none()
        self.group_instance = self.group_query.first()

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
        if not group_instance.path:
            return ""

        parent_path = Path(group_instance.path).parent
        if not self.is_admin():
            try:
                # remove library path for not admins
                library_path_parent = Path(group_instance.library.path).parent
                parent_path = parent_path.relative_to(library_path_parent)
            except ValueError:
                parent_path = ""

        parent_path_str = str(parent_path)
        parent_path_str = parent_path_str.removeprefix(".")
        if parent_path_str and parent_path_str[0] != sep:
            parent_path_str = sep + parent_path_str
        return parent_path_str

    def _get_browser_page_title(self):
        """Get the proper title for this browse level."""
        group_count = 0
        group_name = ""
        pks = self.kwargs.get("pks")
        if not pks:
            group_name = self._get_root_group_name()
        else:
            group_instance = self.group_instance
            if group_instance:
                if isinstance(group_instance, Volume):
                    group_count = group_instance.series.volume_count
                elif isinstance(group_instance, Comic):
                    group_count = group_instance.volume.issue_count
                group_name = group_instance.name

        return {
            "group_name": group_name,
            "group_count": group_count,
        }

    def _check_page_in_bounds(self, total_count):
        """Redirect page out of bounds."""
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page", 1)
        num_pages = ceil(total_count / MAX_OBJ_PER_PAGE)
        if (not pks and page == 1) or (page >= 1 and page <= num_pages):
            # Don't redirect if on the root page for the group.
            # Or page within valid range.
            return num_pages

        # Adjust route mask for redirect
        group = self.kwargs.get("group")
        if num_pages and page > 1:
            # Try page 1 first.
            new_page = num_pages if num_pages and page > num_pages else 1
            pks = pks if pks else "0"
        else:
            # Redirect to root for the group.
            pks = "0"
            new_page = 1

        reason = f"{page=} does not exist!"
        route_changes = {"group": group, "pks": pks, "page": new_page}
        return self._raise_redirect(reason, route_mask=route_changes)

    def _paginate_section(self, model, qs, page):
        """Paginate a group or Comic section."""
        orphans = 0 if self.model_group == "f" or self.params.get("q") else 5
        paginator = Paginator(qs, MAX_OBJ_PER_PAGE, orphans=orphans)
        try:
            qs = paginator.page(page).object_list
        except EmptyPage:
            if model != Folder:
                model_name = self.model.__name__ if self.model else "NO_MODEL"
                LOG.warning(f"No {model_name}s on page {page}")
            qs = model.objects.none()

        return qs

    def _paginate_groups(self, group_qs, total_group_count):
        """Paginate the group object list before books."""
        if total_group_count:
            page = self.kwargs.get("page", 1)
            page_group_qs = self._paginate_section(self.model, group_qs, page)
        else:
            page_group_qs = self.model.objects.none()  # type: ignore
        return page_group_qs

    def _paginate_books(self, book_qs, total_group_count, page_obj_count):
        """Paginate the book object list based on how many group/folders are showing."""
        if page_obj_count >= MAX_OBJ_PER_PAGE:
            # No books for this page
            page_book_qs = Comic.objects.none()
        else:
            group_remainder = total_group_count % MAX_OBJ_PER_PAGE
            if page_obj_count:
                # There are books after the groups on the same page
                # Manually add books without the paginator
                book_limit = MAX_OBJ_PER_PAGE - group_remainder
                page_book_qs = book_qs[:book_limit]
            else:
                # There are books after the groups on a new page
                if group_remainder:
                    book_offset = MAX_OBJ_PER_PAGE - group_remainder
                    page_book_qs = book_qs[book_offset:]
                else:
                    page_book_qs = book_qs

                num_group_and_mixed_pages = ceil(total_group_count / MAX_OBJ_PER_PAGE)
                book_only_page = self.kwargs.get("page", 1) - num_group_and_mixed_pages
                page_book_qs = self._paginate_section(
                    Comic, page_book_qs, book_only_page
                )
        return page_book_qs

    def _paginate(self, group_qs, book_qs, group_count, book_count):
        """Paginate the queryset into a group and book object lists."""
        num_pages = self._check_page_in_bounds(group_count + book_count)
        page_group_qs = self._paginate_groups(group_qs, group_count)
        page_group_count = page_group_qs.count()
        page_book_qs = self._paginate_books(book_qs, group_count, page_group_count)
        page_book_count = page_book_qs.count()

        return page_group_qs, page_book_qs, num_pages, page_group_count, page_book_count

    @staticmethod
    def _get_zero_pad(book_qs):
        """Get the zero padding for the display."""
        issue_number_max = book_qs.only("issue_number").aggregate(Max("issue_number"))[
            "issue_number__max"
        ]
        zero_pad = 1
        if issue_number_max:
            zero_pad += floor(log10(issue_number_max))
        return zero_pad

    def _get_group_and_books(self):
        """Create the main queries with filters, annotation and pagination."""
        group_qs, group_count = self._get_group_queryset()
        book_qs, book_count = self._get_book_queryset()
        # Paginate
        group_qs, book_qs, num_pages, page_group_count, page_book_count = (
            self._paginate(group_qs, book_qs, group_count, book_count)
        )
        if page_group_count:
            group_qs = self.annotate_card_aggregates(group_qs, self.model)
        if page_book_count:
            zero_pad = self._get_zero_pad(book_qs)
            book_qs = self.annotate_card_aggregates(book_qs, Comic)
        else:
            zero_pad = 1

        # print(group_qs.explain())
        # print(group_qs.query)

        recovered_group_list = self.re_cover_multi_groups(group_qs)
        total_count = page_group_count + page_book_count
        return recovered_group_list, book_qs, num_pages, total_count, zero_pad

    def get_object(self):
        """Validate settings and get the querysets."""
        group_list, book_qs, num_pages, total_count, zero_pad = (
            self._get_group_and_books()
        )

        # get additional context
        parent_breadcrumbs = self.get_parent_breadcrumbs()
        title = self._get_browser_page_title()
        # needs to happen after pagination
        # runs obj list query twice :/
        libraries_exist = Library.objects.exists()
        covers_timestamp = int(
            Timestamp.objects.get(
                key=Timestamp.TimestampChoices.COVERS.value
            ).updated_at.timestamp()
        )

        # construct final data structure
        return MappingProxyType(
            {
                "breadcrumbs": parent_breadcrumbs,
                "title": title,
                "model_group": self.model_group,
                "groups": group_list,
                "books": book_qs,
                "zero_pad": zero_pad,
                "num_pages": num_pages,
                "total_count": total_count,
                "admin_flags": self.admin_flags,
                "libraries_exist": libraries_exist,
                "covers_timestamp": covers_timestamp,
            }
        )

    def _get_valid_browse_top_groups(self):
        """Get valid top groups for the current settings.

        Valid top groups are determined by the Browser Settings.
        """
        valid_top_groups = []

        show = self.params["show"]
        for nav_group, allowed in show.items():
            if allowed:
                valid_top_groups.append(nav_group)
        # Issues is always a valid top group
        valid_top_groups += [self.COMIC_GROUP]

        return valid_top_groups

    def _validate_top_group(self, valid_top_groups):
        nav_group = self.kwargs.get("group")
        top_group = self.params.get("top_group")
        if top_group not in valid_top_groups:
            reason = f"top_group {top_group} not in valid nav groups, changed to "
            if nav_group in valid_top_groups:
                valid_top_group = nav_group
                reason += "nav group: "
            else:
                valid_top_group = valid_top_groups[0]
                reason += "first valid top group "
            reason += valid_top_group
            pks = self.kwargs.get("pks", ())
            page = self.kwargs["page"]
            route = {"group": nav_group, "pks": pks, "page": page}
            settings_mask = {"top_group": valid_top_group}
            self._raise_redirect(reason, route, settings_mask)

    def set_valid_browse_nav_groups(self, valid_top_groups):
        """Get valid nav groups for the current settings.

        Valid nav groups are the top group and below that are also
        enabled in browser settings.

        May always navigate to root 'r' nav group.
        """
        top_group = self.params["top_group"]
        nav_group = self.kwargs["group"]
        valid_nav_groups = [self.ROOT_GROUP]

        for possible_index, possible_nav_group in enumerate(valid_top_groups):
            if top_group == possible_nav_group:
                # all the nav groups past this point,
                # 'c' is obscured by the web reader url, but valid for opds
                tail_top_groups = valid_top_groups[possible_index:]
                valid_nav_groups += tail_top_groups

                if nav_group not in valid_nav_groups:
                    reason = (
                        f"Nav group {nav_group} unavailable, "
                        f"redirect to {self.ROOT_GROUP}"
                    )
                    self._raise_redirect(reason)
                break
        self.valid_nav_groups = tuple(valid_nav_groups)

    def _validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        if not self.admin_flags["folder_view"]:
            reason = "folder view disabled"
            valid_top_groups = self._get_valid_browse_top_groups()
            settings_mask = {"top_group": valid_top_groups[0]}
            self._raise_redirect(reason, settings_mask=settings_mask)

        valid_top_groups = (self.FOLDER_GROUP,)
        self._validate_top_group(valid_top_groups)
        self.valid_nav_groups = valid_top_groups

    def _validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        # Validate Browser top_group
        # Change top_group if its not in the valid top groups
        valid_top_groups = self._get_valid_browse_top_groups()
        self._validate_top_group(valid_top_groups)

        # Validate pks
        nav_group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        if nav_group == self.ROOT_GROUP and (pks and 0 not in pks):
            # r never has pks
            reason = f"Redirect r with {pks=} to pks 0"
            self._raise_redirect(reason)

        # Validate Browser nav_group
        # Redirect if nav group is wrong
        self.set_valid_browse_nav_groups(valid_top_groups)

    def _validate_story_arc_settings(self):
        """Validate story arc settings."""
        valid_top_groups = (self.STORY_ARC_GROUP,)
        self._validate_top_group(valid_top_groups)
        self.valid_nav_groups = valid_top_groups

    def validate_settings(self):
        """Validate group and top group settings."""
        group = self.kwargs["group"]
        if group == self.FOLDER_GROUP:
            self._validate_folder_settings()
        elif group == self.STORY_ARC_GROUP:
            self._validate_story_arc_settings()
        else:
            self._validate_browser_group_settings()

        # Validate order
        if self.order_key == "filename" and not self.admin_flags["folder_view"]:
            pks = self.kwargs["pks"]
            page = self.kwargs["page"]
            route_changes = {"group": group, "pks": pks, "page": page}
            reason = "order by filename not allowed by admin flag."
            settings_mask = {"order_by": "sort_name"}
            self._raise_redirect(reason, route_changes, settings_mask)

    def init_request(self):
        """Initialize request."""
        super().init_request()
        self._set_group_query_and_instance()

    @extend_schema(request=BrowserBreadcrumbsView.input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Get browser settings."""
        self.init_request()
        data = self.get_object()
        serializer = self.get_serializer(data)
        self.save_params_to_session(self.params)
        return Response(serializer.data)
