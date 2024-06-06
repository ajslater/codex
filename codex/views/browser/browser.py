"""Views for browsing comic library."""

from math import floor, log10
from types import MappingProxyType
from typing import TYPE_CHECKING

from django.db.models import Max
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

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
    Volume,
)
from codex.serializers.browser.page import BrowserPageSerializer
from codex.util import max_none
from codex.views.browser.title import BrowserTitleView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    STORY_ARC_GROUP,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


LOG = get_logger(__name__)


class BrowserView(BrowserTitleView):
    """Browse comics with a variety of filters and sorts."""

    serializer_class = BrowserPageSerializer

    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
            AdminFlag.FlagChoices.IMPORT_METADATA.value: "import_metadata",
        }
    )
    TARGET = "browser"
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

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.is_opds_2_acquisition = False
        self.group_query: QuerySet = Comic.objects.none()
        self.valid_nav_groups: tuple[str, ...] = ()

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
                    self.raise_redirect(reason, route_mask={"group": group})
        elif self.group_class:
            self.group_query = self.group_class.objects.none()
        else:
            self.group_query = Comic.objects.none()
        self.group_instance = self.group_query.first()

    def init_request(self):
        """Initialize request."""
        super().init_request()
        self._set_group_query_and_instance()

    def get_model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        group = self.kwargs["group"]
        if group == FOLDER_GROUP:
            return group
        if group == STORY_ARC_GROUP:
            pks = self.kwargs.get("pks")
            return COMIC_GROUP if pks else group
        if group == self.valid_nav_groups[-1]:
            # special case for lowest valid group
            return COMIC_GROUP
        return self.valid_nav_groups[self.valid_nav_groups.index(group) + 1]

    ################
    # MAIN QUERIES #
    ################
    def _get_common_queryset(self, model):
        """Create queryset common to group & books."""
        qs = self.get_filtered_queryset(model)
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

    def _get_page_mtime(self, group_qs):
        if self.group_instance:
            page_updated_at_max = self.group_instance.updated_at
        else:
            page_updated_at_max = group_qs.aggregate(max=Max("updated_at"))["max"]

        agg_func = self.get_bookmark_updated_at_aggregate(self.model, True)
        page_bookmark_updated_at = group_qs.aggregate(max=agg_func)["max"]

        return max_none(page_updated_at_max, page_bookmark_updated_at)

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
        mtime = self._get_page_mtime(group_qs)
        book_qs, book_count = self._get_book_queryset()
        # Paginate
        group_qs, book_qs, num_pages, page_group_count, page_book_count = self.paginate(
            group_qs, book_qs, group_count, book_count
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

        total_count = page_group_count + page_book_count
        return group_qs, book_qs, num_pages, total_count, zero_pad, mtime

    def get_object(self):
        """Validate settings and get the querysets."""
        group_qs, book_qs, num_pages, total_count, zero_pad, mtime = (
            self._get_group_and_books()
        )

        # get additional context
        parent_breadcrumbs = self.get_parent_breadcrumbs()
        title = self.get_browser_page_title()
        # needs to happen after pagination
        # runs obj list query twice :/
        libraries_exist = Library.objects.filter(covers_only=False).exists()

        # construct final data structure
        return MappingProxyType(
            {
                "breadcrumbs": parent_breadcrumbs,
                "title": title,
                "model_group": self.model_group,
                "groups": group_qs,
                "books": book_qs,
                "zero_pad": zero_pad,
                "num_pages": num_pages,
                "total_count": total_count,
                "admin_flags": self.admin_flags,
                "libraries_exist": libraries_exist,
                "mtime": mtime,
            }
        )

    @extend_schema(request=BrowserTitleView.input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Get browser settings."""
        self.init_request()
        data = self.get_object()
        serializer = self.get_serializer(data)
        self.save_params_to_session(self.params)
        return Response(serializer.data)
