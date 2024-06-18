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
    Volume,
)
from codex.serializers.browser.page import BrowserPageSerializer
from codex.views.browser.title import BrowserTitleView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    NONE_DATETIMEFIELD,
    STORY_ARC_GROUP,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


LOG = get_logger(__name__)
_GROUP_INSTANCE_SELECT_RELATED: MappingProxyType[
    type[BrowserGroupModel], tuple[str | None, ...]
] = MappingProxyType(
    {
        Comic: ("series", "volume"),
        Volume: ("series",),
        Imprint: ("publisher",),
    }
)


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
                    _GROUP_INSTANCE_SELECT_RELATED.get(self.group_class, (None,))
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
                    settings_mask = {"breadcrumbs": []}
                    self.raise_redirect(
                        reason, route_mask={"group": group}, settings_mask=settings_mask
                    )
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
        count_qs = self.add_group_by(qs, model)
        count = count_qs.count()

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
            qs = self.add_group_by(qs)
        return qs, count

    def _get_book_queryset(self):
        """Create book queryset."""
        if self.model in (Comic, Folder):
            qs, count = self._get_common_queryset(Comic)
        else:
            qs = Comic.objects.none()
            count = 0
        return qs, count

    def _requery_max_bookmark_updated_at(self, group_qs):
        """Get max updated at without bookmark filter and aware of multi-groups."""
        if not self.is_bookmark_filtered:
            return group_qs

        bm_rel, bm_filter = self.get_bookmark_rel_and_filter(self.model)
        bm_updated_at_rel = f"{bm_rel}__updated_at"
        max_bmua = Max(bm_updated_at_rel, default=NONE_DATETIMEFIELD, filter=bm_filter)

        group_list = []
        for group in group_qs:
            qs = self.get_filtered_queryset(
                self.model, bookmark_filter=False, group_filter=False
            )
            group.max_bookmark_updated_at = qs.aggregate(max=max_bmua)["max"]
            group_list.append(group)
        return group_list

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

    def _get_page_mtime(self):
        if not self.is_bookmark_filtered and self.group_instance:
            # Nice optimization if we can get get it.
            return self.group_instance.updated_at

        group_model = self.group_class if self.group_class else self.model
        return self.get_group_mtime(group_model, page_mtime=True)

    def _get_group_and_books(self):
        """Create the main queries with filters, annotation and pagination."""
        group_qs, group_count = self._get_group_queryset()
        book_qs, book_count = self._get_book_queryset()
        # Paginate
        group_qs, book_qs, num_pages, page_group_count, page_book_count = self.paginate(
            group_qs, book_qs, group_count, book_count
        )
        if page_group_count:
            group_qs = self.annotate_card_aggregates(group_qs, self.model)
            group_qs = self._requery_max_bookmark_updated_at(group_qs)
        if page_book_count:
            zero_pad = self._get_zero_pad(book_qs)
            book_qs = self.annotate_card_aggregates(book_qs, Comic)
        else:
            zero_pad = 1

        # print(group_qs.explain())
        # print(group_qs.query)

        total_count = page_group_count + page_book_count
        mtime = self._get_page_mtime()
        return group_qs, book_qs, num_pages, total_count, zero_pad, mtime

    def get_object(self):
        """Validate settings and get the querysets."""
        group_qs, book_qs, num_pages, total_count, zero_pad, mtime = (
            self._get_group_and_books()
        )

        # get additional context
        breadcrumbs = self.get_breadcrumbs()
        title = self.get_browser_page_title()
        # needs to happen after pagination
        # runs obj list query twice :/
        libraries_exist = Library.objects.filter(covers_only=False).exists()

        # construct final data structure
        return MappingProxyType(
            {
                "breadcrumbs": breadcrumbs,
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

    @extend_schema(parameters=[BrowserTitleView.input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get browser settings."""
        self.init_request()
        data = self.get_object()
        serializer = self.get_serializer(data)
        return Response(serializer.data)
