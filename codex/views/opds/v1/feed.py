"""OPDS v1 feed."""

from collections.abc import Callable, Sequence
from functools import wraps
from typing import TYPE_CHECKING, Any, override

from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v1 import OPDS1TemplateSerializer
from codex.settings import BROWSER_MAX_OBJ_PER_PAGE, FALSY
from codex.version import VERSION
from codex.views.opds.const import AUTHOR_ROLES, BLANK_TITLE
from codex.views.opds.metadata import (
    get_credit_people_by_comic,
    get_m2m_objects_by_comic,
)
from codex.views.opds.start import OPDSStartViewMixin
from codex.views.opds.v1.const import OPDS1EntryData, OpdsNs, RootTopLinks
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.links import OPDS1LinksView

if TYPE_CHECKING:
    from collections.abc import Mapping


def _safe_property(
    label: str,
    *,
    default: Any = None,
    default_factory: Callable[[], Any] | None = None,
):
    """
    Decorate an OPDS-feed property accessor to log + swallow exceptions.

    The OPDS template renders a partial document if any field
    accessor raises — better to log via ``logger.exception`` and
    return a sane default than to fail the whole feed. Each
    accessor used to inline its own ``try`` / ``except Exception:
    logger.exception(...)`` block; this helper carries the
    pattern in one place.

    :param label: Short tail for the exception log message
        (rendered as ``"Getting OPDS v1 {label}"``).
    :param default: Value returned on exception. Used when
        ``default_factory`` is unset; ``None`` by default.
    :param default_factory: Callable returning the default for
        callers whose default is mutable (e.g. ``list``). Takes
        precedence over ``default``.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self):
            try:
                return func(self)
            except Exception:
                logger.exception(f"Getting OPDS v1 {label}")
                return default_factory() if default_factory else default

        return wrapper

    return decorator


class OPDS1FeedView(OPDS1LinksView):
    """OPDS 1 Feed."""

    template_name = "opds_v1/index.xml"
    serializer_class: type[BaseSerializer] | None = OPDS1TemplateSerializer
    input_serializer_class: type[OPDSSettingsSerializer] = OPDSSettingsSerializer  # pyright: ignore[reportIncompatibleVariableOverride]
    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    @property
    def version(self):
        """Codex version."""
        return VERSION

    @property
    @_safe_property("namespace")
    def opds_ns(self):
        """Dynamic opds namespace."""
        return OpdsNs.ACQUISITION if self.is_opds_acquisition else OpdsNs.CATALOG

    @property
    def is_acquisition(self) -> bool:
        """Is acquisition."""
        return self.is_opds_acquisition

    @property
    @_safe_property("ID Tag")
    def id_tag(self):
        """Feed id is the url."""
        return self.request.build_absolute_uri()

    @property
    @_safe_property("feed title", default="")
    def title(self) -> str:
        """Create the feed title."""
        browser_title: Mapping[str, Any] = self.obj.get("title", {})
        result = ""
        if browser_title:
            parent_name = browser_title.get("parent_name", "All")
            pks = self.kwargs["pks"]
            if not parent_name and not pks:
                parent_name = "All"
            group_name = browser_title.get("group_name")
            result = " ".join(filter(None, (parent_name, group_name))).strip()
        return result or BLANK_TITLE

    @property
    @_safe_property("updated", default="")
    def updated(self) -> str:
        """Use mtime for updated."""
        mtime = self.obj.get("mtime")
        return mtime.isoformat() if mtime else ""

    @property
    @_safe_property("items per page")
    def items_per_page(self) -> int | None:
        """Return opensearch:itemsPerPage."""
        if self.params.get("search"):
            return BROWSER_MAX_OBJ_PER_PAGE
        return None

    @property
    @_safe_property("total results")
    def total_results(self):
        """Return opensearch:totalResults."""
        if self.params.get("search"):
            return self.obj.get("total_count", 0)
        return None

    def _get_entries_section(self, key, metadata) -> list:
        """Get entries by key section."""
        entries = []
        if objs := self.obj.get(key):
            zero_pad: int = self.obj["zero_pad"]
            # Pre-compute the per-page M2M batches when this section is
            # the books section AND ?opdsMetadata=1 is requested. Each
            # OPDS1Entry's ``authors`` / ``contributors`` /
            # ``category_groups`` properties otherwise fire 9 queries
            # per entry (sub-plan 03 #1) — at 100+ entries the worst
            # case is 900+ queries on a single feed page. The batched
            # helpers UNION the M2M tables and partition in Python so
            # the cost collapses to 3 queries total per feed page.
            authors_by_pk = contributors_by_pk = category_groups_by_pk = None
            if metadata and key == "books":
                all_pks = [obj.pk for obj in objs]
                authors_by_pk = get_credit_people_by_comic(
                    all_pks, AUTHOR_ROLES, exclude=False
                )
                contributors_by_pk = get_credit_people_by_comic(
                    all_pks, AUTHOR_ROLES, exclude=True
                )
                category_groups_by_pk = get_m2m_objects_by_comic(all_pks)
            data = OPDS1EntryData(
                self.opds_acquisition_groups,
                zero_pad,
                metadata,
                self.mime_type_map,
                authors_by_pk=authors_by_pk,
                contributors_by_pk=contributors_by_pk,
                category_groups_by_pk=category_groups_by_pk,
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
    @_safe_property("entries", default_factory=list)
    def entries(self) -> list:
        """Create all the entries."""
        entries = []
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
        return entries

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs) -> Response:
        """Get the feed."""
        serializer = self.get_serializer(self)
        self.mark_user_active()
        return Response(serializer.data, content_type=self.content_type)


class OPDS1StartView(OPDSStartViewMixin, OPDS1FeedView):
    """OPDS v1 Start Page."""

    @override
    @extend_schema(
        parameters=[OPDS1FeedView.input_serializer_class],
        operation_id="opds_1.2_start_retrieve",
    )
    def get(self, *args, **kwargs) -> Response:
        return super().get(*args, **kwargs)
