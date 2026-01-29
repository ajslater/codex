"""OPDS v1 feed."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from typing_extensions import override

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v1 import OPDS1TemplateSerializer
from codex.settings import FALSY, MAX_OBJ_PER_PAGE
from codex.views.opds.const import BLANK_TITLE, DEFAULT_PARAMS
from codex.views.opds.v1.const import OPDS1EntryData, OpdsNs, RootTopLinks
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.links import OPDS1LinksView

if TYPE_CHECKING:
    from collections.abc import Mapping


class OPDS1FeedView(OPDS1LinksView):
    """OPDS 1 Feed."""

    template_name = "opds_v1/index.xml"
    serializer_class: type[BaseSerializer] | None = OPDS1TemplateSerializer
    input_serializer_class: type[OPDSSettingsSerializer] = OPDSSettingsSerializer  # pyright: ignore[reportIncompatibleVariableOverride]
    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    @property
    def opds_ns(self):
        """Dynamic opds namespace."""
        try:
            return OpdsNs.ACQUISITION if self.is_opds_acquisition else OpdsNs.CATALOG
        except Exception:
            logger.exception("Getting OPDS v1 namespace")

    @property
    def is_acquisition(self):
        """Is acquisition."""
        return self.is_opds_acquisition

    @property
    def id_tag(self):
        """Feed id is the url."""
        try:
            return self.request.build_absolute_uri()
        except Exception:
            logger.exception("Getting OPDS v1 ID Tag")

    @property
    def title(self):
        """Create the feed title."""
        result = ""
        try:
            browser_title: Mapping[str, Any] = self.obj.get("title", {})
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
            logger.exception("Getting OPDS v1 feed title")
        return result

    @property
    def updated(self):
        """Use mtime for updated."""
        datestr = ""
        try:
            mtime = self.obj.get("mtime")
            if mtime:
                datestr = mtime.isoformat()
        except Exception:
            logger.exception("Getting OPDS v1 updated")
        return datestr

    @property
    def items_per_page(self):
        """Return opensearch:itemsPerPage."""
        try:
            if self.params.get("q"):
                return MAX_OBJ_PER_PAGE
        except Exception:
            logger.exception("Getting OPDS v1 items per page")

    @property
    def total_results(self):
        """Return opensearch:totalResults."""
        try:
            if self.params.get("q"):
                return self.obj.get("total_count", 0)
        except Exception:
            logger.exception("Getting OPDS v1 total results")

    def _get_entries_section(self, key, metadata):
        """Get entries by key section."""
        entries = []
        if objs := self.obj.get(key):
            zero_pad: int = self.obj["zero_pad"]
            data = OPDS1EntryData(
                self.opds_acquisition_groups, zero_pad, metadata, self.mime_type_map
            )
            fallback = bool(self.admin_flags.get("folder_view"))
            import_pks = set()
            for obj in objs:
                entry = OPDS1Entry(
                    obj,
                    self.request.GET,
                    data,
                    title_filename_fallback=fallback,
                )
                if key == "books" and entry.lazy_metadata():
                    import_pks.add(obj.pk)
                entries.append(entry)
            if import_pks:
                task = LazyImportComicsTask(group="c", pks=frozenset(import_pks))
                LIBRARIAN_QUEUE.put(task)
        return entries

    @property
    def entries(self):
        """Create all the entries."""
        entries = []
        try:
            # if not self.use_facets:  # and self.kwargs.get("page") == 1:
            facet_entries = not self.use_facets
            if self.IS_START_PAGE:
                entries += self.add_top_links(RootTopLinks.ALL)
            else:
                entries += self.add_start_link()

            entries += self.facets(entries=facet_entries)

            if not self.IS_START_PAGE:
                entries += self._get_entries_section("groups", metadata=False)
                metadata = self.request.GET.get("opdsMetadata", "").lower() not in FALSY
                entries += self._get_entries_section("books", metadata)
        except Exception:
            logger.exception("Getting OPDS v1 entries")
        return entries

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        serializer = self.get_serializer(self)
        self.mark_user_active()
        return Response(serializer.data, content_type=self.content_type)


class OPDS1StartView(OPDS1FeedView):
    """OPDS v1 Start Page."""

    IS_START_PAGE = True

    def __init__(self, *args, **kwargs):
        """Reset all params."""
        super().__init__(*args, **kwargs)
        self.set_params(DEFAULT_PARAMS)

    @override
    @extend_schema(
        parameters=[OPDS1FeedView.input_serializer_class],
        operation_id="opds_1.2_start_retrieve",
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)
