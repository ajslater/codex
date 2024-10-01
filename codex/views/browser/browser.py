"""Views for browsing comic library."""

from math import ceil, floor, log10
from types import MappingProxyType

from django.db.models import Max
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Library,
)
from codex.serializers.browser.page import BrowserPageSerializer
from codex.views.browser.title import BrowserTitleView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    MAX_OBJ_PER_PAGE,
    STORY_ARC_GROUP,
)

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

    ########
    # Init #
    ########

    @property
    def model_group(self):
        """Get the group of the models to browse."""
        # the model group shown must be:
        #   A valid nav group or 'c'
        #   the child of the current nav group or 'c'
        if not self._model_group:
            group = self.kwargs["group"]
            if group == FOLDER_GROUP:
                self._model_group = group
            elif group == STORY_ARC_GROUP:
                pks = self.kwargs.get("pks")
                self._model_group = COMIC_GROUP if pks else group
            elif group == self.valid_nav_groups[-1]:
                # special case for lowest valid group
                self._model_group = COMIC_GROUP
            else:
                self._model_group = self.valid_nav_groups[
                    self.valid_nav_groups.index(group) + 1
                ]
        return self._model_group

    ################
    # MAIN QUERIES #
    ################

    def _get_limit(self):
        """Get the limit for the query."""
        # query_limit only is set by some opds views
        query_limit = self.params.get("limit", 0)
        search_limit = self.get_search_limit()
        if query_limit and search_limit:
            limit = min(query_limit, search_limit)
        else:
            limit = max(query_limit, search_limit)
        return limit

    def _get_common_queryset(self, model):
        """Create queryset common to group & books."""
        qs = self.get_filtered_queryset(model)
        limit = self._get_limit()
        try:
            count_qs = self.add_group_by(qs)
            if limit:
                count_qs = count_qs[:limit]
            # Get count after filters and before any annotations or orders
            #   because it's faster. These counts are used by
            #   is_page_in_bounds(), num_pages for the nav bar, and paginate()
            count = count_qs.count()
        except OperationalError as exc:
            self._handle_operational_error(exc)
            count = 0
            qs = model.objects.none()

        if count:
            qs = self.annotate_order_aggregates(qs)
            qs = self.add_order_by(qs)
            if limit:
                qs = qs[:limit]
        else:
            qs = qs.order_by("pk")

        return qs, count

    def _get_group_queryset(self):
        """Create group queryset."""
        if self.model is Comic:
            qs = self.model.objects.none().order_by("pk")
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
            qs = Comic.objects.none().order_by("pk")
            count = 0
        return qs, count

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
        return self.get_group_mtime(self.model, page_mtime=True)

    def _debug_queries(self, group_count, book_count, group_qs, book_qs):
        """Log query details."""
        if group_count:
            LOG.debug(group_qs.explain())
            LOG.debug(group_qs.query)
        if book_count:
            LOG.debug(book_qs.explain())
            LOG.debug(book_qs.query)

    def _get_group_and_books(self):
        """Create the main queries with filters, annotation and pagination."""
        group_qs, group_count = self._get_group_queryset()
        book_qs, book_count = self._get_book_queryset()

        # Paginate
        num_pages = ceil((group_count + book_count) / MAX_OBJ_PER_PAGE)
        self.check_page_in_bounds(num_pages)
        group_qs, book_qs, page_group_count, page_book_count = self.paginate(
            group_qs, book_qs, group_count
        )

        # Annotate
        if page_group_count:
            group_qs = self.annotate_card_aggregates(group_qs)
            group_qs = self.force_inner_joins(group_qs)
        if page_book_count:
            zero_pad = self._get_zero_pad(book_qs)
            book_qs = self.annotate_card_aggregates(book_qs)
            book_qs = self.force_inner_joins(book_qs)
        else:
            zero_pad = 1

        # self._debug_queries(page_group_count, page_book_count, group_qs, book_qs)

        total_page_count = page_group_count + page_book_count
        mtime = self._get_page_mtime()
        return group_qs, book_qs, num_pages, total_page_count, zero_pad, mtime

    def get_object(self):  # type: ignore
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
                "search_error": self.search_error,
                "fts": self.fts_mode,
            }
        )

    @extend_schema(parameters=[BrowserTitleView.input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get browser settings."""
        data = self.get_object()
        serializer = self.get_serializer(data)
        return Response(serializer.data)
