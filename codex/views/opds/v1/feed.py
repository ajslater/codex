"""OPDS v1 feed."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from comicbox.box import Comicbox
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v1 import (
    OPDS1TemplateSerializer,
)
from codex.views.const import FALSY, MAX_OBJ_PER_PAGE
from codex.views.opds.auth import OPDSTemplateView
from codex.views.opds.const import BLANK_TITLE, MimeType
from codex.views.opds.v1.entry.data import OPDS1EntryData
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.links import (
    OPDS1LinksView,
    RootTopLinks,
    TopLinks,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet

LOG = get_logger(__name__)


class OpdsNs:
    """XML Namespaces."""

    CATALOG = "http://opds-spec.org/2010/catalog"
    ACQUISITION = "http://opds-spec.org/2010/acquisition"


class UserAgentNames:
    """Control whether to hack in facets with nav links."""

    CLIENT_REORDERS = frozenset({"Chunky"})
    FACET_SUPPORT = frozenset({"yar"})  # kybooks
    SIMPLE_DOWNLOAD_MIME_TYPES = frozenset({"PocketBook Reader"})
    # Other known valid  names:
    # "Panels", "Chunky"


class OPDS1FeedView(OPDS1LinksView, OPDSTemplateView):
    """OPDS 1 Feed."""

    template_name = "opds_v1/index.xml"
    serializer_class = OPDS1TemplateSerializer
    input_serializer_class = OPDSSettingsSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "opds"
    TARGET = "opds1"

    @property
    def opds_ns(self):
        """Dynamic opds namespace."""
        try:
            return OpdsNs.ACQUISITION if self.is_aq_feed else OpdsNs.CATALOG
        except Exception:
            LOG.exception("Getting OPDS v1 namespace")

    @property
    def is_acquisition(self):
        """Is acquisition."""
        return self.is_aq_feed

    @property
    def id_tag(self):
        """Feed id is the url."""
        try:
            return self.request.build_absolute_uri()
        except Exception:
            LOG.exception("Getting OPDS v1 ID Tag")

    @property
    def title(self):
        """Create the feed title."""
        result = ""
        try:
            browser_title: Mapping[str, Any] = self.obj.get("title")  # type: ignore
            if browser_title:
                parent_name = browser_title.get("parent_name", "All")
                pks = self.kwargs["pks"]
                if not parent_name and not pks:
                    parent_name = "All"
                group_name = browser_title.get("group_name")
                result = " ".join(filter(None, (parent_name, group_name))).strip()

            if not result:
                result = BLANK_TITLE
        except Exception:
            LOG.exception("Getting OPDS v1 feed title")
        return result

    @property
    def updated(self):
        """Use mtime for updated."""
        try:
            return self.obj.get("mtime", "")
        except Exception:
            LOG.exception("Getting OPDS v1 updated")

    @property
    def items_per_page(self):
        """Return opensearch:itemsPerPage."""
        try:
            if self.params.get("q"):
                return MAX_OBJ_PER_PAGE
        except Exception:
            LOG.exception("Getting OPDS v1 items per page")

    @property
    def total_results(self):
        """Return opensearch:totalResults."""
        try:
            if self.params.get("q"):
                return self.obj.get("total_count", 0)
        except Exception:
            LOG.exception("Getting OPDS v1 total results")

    def _get_entries_section(self, key, metadata):
        """Get entries by key section."""
        entries = []
        if objs := self.obj.get(key):
            zero_pad: int = self.obj["zero_pad"]  # type: ignore
            data = OPDS1EntryData(
                self.acquisition_groups, zero_pad, metadata, self.mime_type_map
            )
            fallback = bool(self.admin_flags.get("folder_view"))
            for obj in objs:  # type: ignore
                entries += [
                    OPDS1Entry(
                        obj,
                        self.request.GET,
                        data,
                        title_filename_fallback=fallback,
                    )
                ]
        return entries

    @property
    def entries(self):
        """Create all the entries."""
        entries = []
        try:
            if not self.use_facets and self.kwargs.get("page") == 1:
                entries += self.add_top_links(TopLinks.ALL)
                at_root = not self.kwargs["pks"]
                if at_root:
                    entries += self.add_top_links(RootTopLinks.ALL)
                entries += self.facets(entries=True, root=at_root)

            entries += self._get_entries_section("groups", False)
            metadata = self.request.GET.get("opdsMetadata", "").lower() not in FALSY
            entries += self._get_entries_section("books", metadata)
        except Exception:
            LOG.exception("Getting OPDS v1 entries")
        return entries

    def _ensure_page_counts(self):
        """Ensure page counts on books with just in time comicbox."""
        if self.admin_flags.get("import_metadata"):
            return
        books_qs: QuerySet = self.obj["books"]  # type: ignore
        import_pks = set()
        new_books = []
        for book in books_qs:
            if book.page_count is not None:
                continue
            with Comicbox(book.path) as cb:
                book.file_type = cb.get_file_type()
                book.page_count = cb.get_page_count()
            new_books.append(book)
            import_pks.add(book.pk)
        if new_books:
            writable_obj = dict(self.obj)
            writable_obj["books"] = new_books  # type: ignore
            self.obj = MappingProxyType(writable_obj)
            task = LazyImportComicsTask(frozenset(import_pks))
            LIBRARIAN_QUEUE.put(task)

    def get_object(self):  # type: ignore
        """Get the browser page and serialize it for this subclass."""
        group_qs, book_qs, num_pages, total_count, zero_pad, mtime = (
            super()._get_group_and_books()
        )
        book_qs = book_qs.select_related("series", "volume", "language")

        title = self.get_browser_page_title()
        self.obj = MappingProxyType(
            {
                "title": title,
                "groups": group_qs,
                "books": book_qs,
                "zero_pad": zero_pad,
                "num_pages": num_pages,
                "total_count": total_count,
                "mtime": mtime,
            }
        )

        self.is_aq_feed = self.model_group in ("c", "f")

        self._ensure_page_counts()

        # Do not return a Mapping despite the type. Return self for the serializer.
        return self

    def _set_user_agent_variables(self):
        """Set User Agent variables."""
        user_agent = self.request.headers.get("User-Agent")
        if not user_agent:
            return
        user_agent_parts = user_agent.split("/", 1)
        if user_agent_parts:
            user_agent_name = user_agent_parts[0]
        else:
            return

        if user_agent_name in UserAgentNames.FACET_SUPPORT:
            self.use_facets = True
        if user_agent_name in UserAgentNames.CLIENT_REORDERS:
            self.skip_order_facets = True
        if user_agent_name in UserAgentNames.SIMPLE_DOWNLOAD_MIME_TYPES:
            self.mime_type_map = MimeType.SIMPLE_FILE_TYPE_MAP

    def set_opds_request_type(self):
        """Set the opds request type variables."""
        group = self.kwargs.get("group")
        if group == "a":
            self.acquisition_groups = frozenset({"a", "c"})
            pks = self.kwargs["pks"]
            self.is_opds_1_acquisition = group in self.acquisition_groups and pks
        else:
            self.acquisition_groups = frozenset({*self.valid_nav_groups[-2:]} | {"c"})
            self.is_opds_1_acquisition = group in self.acquisition_groups
        self.is_opds_metadata = (
            self.request.GET.get("opdsMetadata", "").lower() not in FALSY
        )

    def init_request(self):
        """Initialize request."""
        super().init_request()
        self.set_opds_request_type()
        self._set_user_agent_variables()
        self.skip_order_facets |= self.kwargs.get("group") == "c"

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        self.init_request()
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, content_type=self.content_type)
