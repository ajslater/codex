"""OPDS v1 feed."""

from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from comicbox.box import Comicbox
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.serializers.opds.v1 import (
    OPDS1TemplateSerializer,
)
from codex.views.browser.browser import BrowserView
from codex.views.browser.const import MAX_OBJ_PER_PAGE
from codex.views.const import FALSY
from codex.views.opds.const import BLANK_TITLE, MimeType
from codex.views.opds.v1.entry.data import OPDS1EntryData
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.links import (
    LinksMixin,
    RootTopLinks,
    TopLinks,
)
from codex.views.template import CodexXMLTemplateView

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet

LOG = get_logger(__name__)


class OpdsNs:
    """XML Namespaces."""

    CATALOG = "http://opds-spec.org/2010/catalog"
    ACQUISITION = "http://opds-spec.org/2010/acquisition"


class UserAgentPrefixes:
    """Control whether to hack in facets with nav links."""

    CLIENT_REORDERS = ("Chunky",)
    FACET_SUPPORT = ("yar",)  # kybooks
    SIMPLE_DOWNLOAD_MIME_TYPES = ("PocketBook",)
    # Other known valid  prefixes:
    # "Panels", "Chunky"


class OPDS1FeedView(CodexXMLTemplateView, LinksMixin):
    """OPDS 1 Feed."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    template_name = "opds_v1/index.xml"
    serializer_class = OPDS1TemplateSerializer

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
            browser_title: Mapping[str, Any] = self.obj.get("browser_title")  # type: ignore
            if browser_title:
                parent_name = browser_title.get("parent_name", "All")
                if not parent_name and self.kwargs.get("pk") == 0:
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
        """Hack in feed update time from cover timestamp."""
        try:
            if ts := self.obj.get("covers_timestamp"):
                return datetime.fromtimestamp(ts, tz=timezone.utc)  # type: ignore
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
            issue_number_max: int = self.obj.get("issue_number_max", 0)  # type: ignore
            data = OPDS1EntryData(
                self.acquisition_groups, issue_number_max, metadata, self.mime_type_map
            )
            fallback = bool(self.admin_flags.get("folder_view"))
            for obj in objs:  # type: ignore
                entries += [
                    OPDS1Entry(
                        obj,
                        self.request.query_params,
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
            at_root = self.kwargs.get("pk") == 0
            if not self.use_facets and self.kwargs.get("page") == 1:
                entries += self.add_top_links(TopLinks.ALL)
                if at_root:
                    entries += self.add_top_links(RootTopLinks.ALL)
                entries += self.facets(entries=True, root=at_root)

            entries += self._get_entries_section("groups", False)
            metadata = (
                self.request.query_params.get("opdsMetadata", "").lower() not in FALSY
            )
            entries += self._get_entries_section("books", metadata)
        except Exception:
            LOG.exception("Getting OPDS v1 entries")
        return entries

    def _ensure_page_counts(self):
        """Ensure page counts on books with just in time comicbox."""
        books_qs: QuerySet = self.obj["books"]  # type: ignore
        import_pks = set()
        new_books = []
        for book in books_qs:
            if not book.page_count:
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
        group = self.kwargs.get("group")
        if group == "a":
            self.acquisition_groups = frozenset({"a", "c"})
            pk = self.kwargs.get("pk")
            self.is_opds_1_acquisition = group in self.acquisition_groups and pk
        else:
            self.acquisition_groups = frozenset({*self.valid_nav_groups[-2:]} | {"c"})
            self.is_opds_1_acquisition = group in self.acquisition_groups
        self.is_opds_metadata = (
            self.request.query_params.get("opdsMetadata", "").lower() not in FALSY
        )
        self.obj = super().get_object()
        self.is_aq_feed = self.model_group in ("c", "f")

        self._ensure_page_counts()

        # Do not return a Mapping despite the type. Return self for the serializer.
        return self

    def _set_user_agent_variables(self):
        """Set User Agent variables."""
        # defaults in FacetsMixin
        user_agent = self.request.headers.get("User-Agent")
        if not user_agent:
            return
        for prefix in UserAgentPrefixes.FACET_SUPPORT:
            if user_agent.startswith(prefix):
                self.use_facets = True
                break
        for prefix in UserAgentPrefixes.CLIENT_REORDERS:
            if user_agent.startswith(prefix):
                self.skip_order_facets = True
                break
        for prefix in UserAgentPrefixes.SIMPLE_DOWNLOAD_MIME_TYPES:
            if user_agent.startswith(prefix):
                self.mime_type_map = MimeType.SIMPLE_FILE_TYPE_MAP
                break

    @extend_schema(
        request=BrowserView.input_serializer_class,
        parameters=[BrowserView.input_serializer_class],
    )
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        self.parse_params()
        self.validate_settings()
        self._set_user_agent_variables()
        self.skip_order_facets |= self.kwargs.get("group") == "c"

        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, content_type=self.content_type)
