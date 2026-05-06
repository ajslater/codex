"""Views for browsing comic library."""

from math import ceil, floor, log10
from types import MappingProxyType
from typing import override

from django.core.cache import cache as _django_cache
from django.db.models import Max
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    Comic,
    Folder,
    Library,
)
from codex.serializers.browser.page import (
    BrowserPageSerializer,
    BrowserTablePageSerializer,
)
from codex.serializers.browser.settings import BrowserPageInputSerializer
from codex.settings import BROWSER_MAX_OBJ_PER_PAGE
from codex.views.browser.columns import default_columns_for
from codex.views.browser.title import BrowserTitleView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    STORY_ARC_GROUP,
)

_LIBRARIES_EXIST_CACHE_KEY = "codex:libraries_exist"
_LIBRARIES_EXIST_TTL_SECONDS = 60


def libraries_exist() -> bool:
    """
    Return whether any non-cover-only library is configured.

    Backed by Django's default cache. Signal handlers in
    ``codex.signals.django_signals`` clear the key on Library writes;
    the TTL bounds staleness across worker processes that don't see the
    signal directly.
    """
    value = _django_cache.get(_LIBRARIES_EXIST_CACHE_KEY)
    if value is None:
        value = Library.objects.filter(covers_only=False).exists()
        _django_cache.set(
            _LIBRARIES_EXIST_CACHE_KEY, value, _LIBRARIES_EXIST_TTL_SECONDS
        )
    return bool(value)


def invalidate_libraries_exist_cache() -> None:
    """Drop the cached libraries_exist value."""
    _django_cache.delete(_LIBRARIES_EXIST_CACHE_KEY)


class BrowserView(BrowserTitleView):
    """Browse comics with a variety of filters and sorts."""

    serializer_class: type[BaseSerializer] | None = BrowserPageSerializer
    input_serializer_class = BrowserPageInputSerializer  # type: ignore[assignment]

    ADMIN_FLAGS = (
        AdminFlagChoices.FOLDER_VIEW,
        AdminFlagChoices.IMPORT_METADATA,
    )
    TARGET: str = "browser"

    ########
    # Init #
    ########

    @property
    @override
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
            elif group == self.valid_nav_groups[-1] or group == COMIC_GROUP:
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

    def _get_common_queryset(self, model) -> tuple:
        """Create queryset common to group & books."""
        qs = self.get_filtered_queryset(model)
        limit = self._get_limit()
        try:
            # Group once here; `add_group_by` is a no-op for Comic so the
            # book path is unaffected, and the group path no longer needs
            # a second call after ordering.
            qs = self.add_group_by(qs)
            count_qs = qs[:limit] if limit else qs
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

    def _get_group_queryset(self) -> tuple:
        """Create group queryset."""
        if self.model is Comic:
            qs = self.model.objects.none().order_by("pk")
            count = 0
        else:
            qs, count = self._get_common_queryset(self.model)
        return qs, count

    def _get_book_queryset(self) -> tuple:
        """Create book queryset."""
        if self.model in (Comic, Folder):
            qs, count = self._get_common_queryset(Comic)
        else:
            qs = Comic.objects.none().order_by("pk")
            count = 0
        return qs, count

    @staticmethod
    def _get_zero_pad(book_qs) -> int:
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

    def _debug_queries(self, group_count, book_count, group_qs, book_qs) -> None:
        """Log query details."""
        if group_count:
            logger.debug(group_qs.explain())
            logger.debug(group_qs.query)
        if book_count:
            logger.debug(book_qs.explain())
            logger.debug(book_qs.query)

    def get_book_qs(self) -> tuple:
        """Only get the book queryset."""
        book_qs, book_count = self._get_book_queryset()
        if book_count:
            # select_related volume would be appropriate but opds doesn't need it.
            book_qs = book_qs.select_related("series")
            zero_pad = self._get_zero_pad(book_qs)
            book_qs = self.annotate_card_aggregates(book_qs)
            book_qs = self.force_inner_joins(book_qs)
        else:
            zero_pad = 0
        return book_qs, book_count, zero_pad

    def _get_group_and_books(self) -> tuple:
        """Create the main queries with filters, annotation and pagination."""
        group_qs, group_count = self._get_group_queryset()
        book_qs, book_count = self._get_book_queryset()

        # Paginate
        num_pages = ceil((group_count + book_count) / BROWSER_MAX_OBJ_PER_PAGE)
        self.check_page_in_bounds(num_pages)
        group_qs, book_qs, page_group_count, page_book_count = self.paginate(
            group_qs, book_qs, group_count, book_count
        )

        # Annotate
        if page_group_count:
            group_qs = self.annotate_card_aggregates(group_qs)
            group_qs = self.annotate_cover(group_qs)
            group_qs = self.force_inner_joins(group_qs)
        if page_book_count:
            zero_pad = self._get_zero_pad(book_qs)
            book_qs = self.annotate_card_aggregates(book_qs)
            book_qs = self.force_inner_joins(book_qs)
        else:
            zero_pad = 1

        # self._debug_queries(page_group_count, page_book_count, group_qs, book_qs) # noqa: ERA001

        total_page_count = page_group_count + page_book_count
        mtime = self._get_page_mtime()
        return group_qs, book_qs, num_pages, total_page_count, zero_pad, mtime

    @override
    def get_object(self) -> MappingProxyType:
        """Validate settings and get the querysets."""
        group_qs, book_qs, num_pages, total_count, zero_pad, mtime = (
            self._get_group_and_books()
        )

        # get additional context
        breadcrumbs = self.get_breadcrumbs()
        title = self.get_browser_page_title()
        # needs to happen after pagination
        # runs obj list query twice :/
        libraries_exist_flag = libraries_exist()
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
                "libraries_exist": libraries_exist_flag,
                "mtime": mtime,
                "search_error": self.search_error,
                "fts": self.fts_mode,
            }
        )

    def _resolve_table_columns(self) -> tuple[str, ...]:
        """
        Pick the column set for this table-view request.

        Priority: explicit ``columns=`` query param (already validated
        and stored on params), then the user's persisted
        ``table_columns[top_group]``, then the registry defaults for
        the current top-group.
        """
        columns = self.params.get("columns") or ()
        if columns:
            return tuple(columns)
        top_group = self.params.get("top_group") or self.kwargs.get("group") or "p"
        stored = self.params.get("table_columns") or {}
        stored_for_group = stored.get(top_group) if isinstance(stored, dict) else None
        if stored_for_group:
            return tuple(stored_for_group)
        return default_columns_for(top_group)

    @extend_schema(parameters=[BrowserTitleView.input_serializer_class])
    def get(self, *_args, **_kwargs) -> Response:
        """Return either a card-grid response or a table-row response."""
        data = self.get_object()
        if self.params.get("view_mode") == "table":
            payload = {**dict(data), "columns": self._resolve_table_columns()}
            serializer = BrowserTablePageSerializer(payload)
        else:
            serializer = self.get_serializer(data)
        return Response(serializer.data)
