"""OPDS v1 Facets methods."""

from types import MappingProxyType
from typing import Any

from django.urls import reverse

from codex.views.opds.const import MimeType, Rel, UserAgentNames
from codex.views.opds.feed import OPDSBrowserView
from codex.views.opds.v1.const import (
    FacetGroups,
    OPDS1EntryData,
    OPDS1EntryObject,
    OPDS1Link,
    RootFacetGroups,
)
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.template import CodexXMLTemplateMixin
from codex.views.util import pop_name


class OPDS1FacetsView(CodexXMLTemplateMixin, OPDSBrowserView):
    """OPDS 1 Facets methods."""

    TARGET = "opds1"
    IS_START_PAGE: bool = False

    def __init__(self, *args, **kwargs) -> None:
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._user_agent_name: str | None = None
        self._mime_type_map: MappingProxyType[str, str] | None = None
        self._use_facets: bool | None = None
        self._obj: MappingProxyType[str, Any] | None = None

    @property
    def mime_type_map(self) -> MappingProxyType[str, str]:
        """Memoize mime type map."""
        if self._mime_type_map is None:
            self._mime_type_map = (
                MimeType.SIMPLE_FILE_TYPE_MAP
                if self.user_agent_name in UserAgentNames.SIMPLE_DOWNLOAD_MIME_TYPES
                else MimeType.FILE_TYPE_MAP
            )
        return self._mime_type_map

    @property
    def use_facets(self) -> bool:
        """Memoize use_facets."""
        if self._use_facets is None:
            self._use_facets = self.user_agent_name in UserAgentNames.FACET_SUPPORT
        return self._use_facets

    @property
    def obj(self) -> MappingProxyType[str, Any]:
        """Get the browser page and serialize it for this subclass."""
        if self._obj is None:
            group_qs, book_qs, num_pages, total_count, zero_pad, mtime = (
                self._get_group_and_books()
            )
            book_qs = book_qs.select_related("series", "volume", "language")

            title = self.get_browser_page_title()
            self._obj = MappingProxyType(
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
        return self._obj

    def _facet(self, kwargs, facet_group, facet_title, new_query_params) -> OPDS1Link:
        kwargs = pop_name(kwargs)
        facet_active = False
        for key, val in new_query_params.items():
            if self.request.GET.get(key) == val:
                facet_active = True
                break
        query = {}
        query.update(self.request.GET)
        query.update(new_query_params)
        href = reverse("opds:v1:feed", kwargs=dict(kwargs), query=query)

        title = " ".join(filter(None, (facet_group.title_prefix, facet_title))).strip()
        return OPDS1Link(
            Rel.FACET,
            href,
            MimeType.NAV,
            title=title,
            facet_group=facet_group.query_param,
            facet_active=facet_active,
        )

    def _facet_entry(self, item, facet_group, facet, query_params) -> OPDS1Entry:
        name = " ".join(
            filter(None, (facet_group.glyph, facet_group.title_prefix, facet.title))
        ).strip()
        entry_obj = OPDS1EntryObject(
            group=item.get("group"),
            ids=item.get("pks"),
            name=name,
        )
        qps = {**self.request.GET}
        qps.update(query_params)
        zero_pad: int = self.obj["zero_pad"]
        data = OPDS1EntryData(
            self.opds_acquisition_groups,
            zero_pad,
            metadata=False,
            mime_type_map=self.mime_type_map,
        )
        return OPDS1Entry(entry_obj, qps, data, title_filename_fallback=False)

    @staticmethod
    def _did_special_group_change(group, facet_group) -> bool:
        """Test if one of the special groups changed."""
        # Special groups are folders ("f") and story arcs ("a").
        # The change is meaningful only if exactly one side is special:
        # XOR-style across membership in the special-group set.
        return (group in "fa") != (facet_group in "fa")

    def _facet_or_facet_entry(self, facet_group, facet, *, entries: bool):
        # This logic preempts facet:activeFacet but no one uses it.
        group = self.kwargs.get("group")
        if facet_group.query_param == "topGroup" and self._did_special_group_change(
            group, facet.value
        ):
            kwargs = {"group": facet.value, "pks": {}, "page": 1}
        else:
            kwargs = self.kwargs

        qps = {facet_group.query_param: facet.value}
        if entries:
            facet = self._facet_entry(kwargs, facet_group, facet, qps)
        else:
            facet = self._facet(kwargs, facet_group, facet.title, qps)
        return facet

    def _facet_group(self, facet_group, *, entries: bool) -> list:
        # Read the folder-view flag once per facet group via the
        # request-cached ``self.admin_flags`` MappingProxyType — the
        # prior code fired ``AdminFlag.objects.get`` per facet inside
        # the loop (sub-plan 02 #6).
        folder_view_allowed = bool(self.admin_flags.get("folder_view"))
        facets = []
        for facet in facet_group.facets:
            if facet.value == "f" and not folder_view_allowed:
                continue
            if facet_obj := self._facet_or_facet_entry(
                facet_group, facet, entries=entries
            ):
                facets += [facet_obj]
        return facets

    def facets(self, *, entries: bool) -> list:
        """Return facets."""
        facets = []
        if self.IS_START_PAGE:
            facets += self._facet_group(RootFacetGroups.TOP_GROUP, entries=entries)
        else:
            group = self.kwargs.get("group")
            if (
                group != "c"
                and self.user_agent_name not in UserAgentNames.CLIENT_REORDERS
            ):
                facets += self._facet_group(FacetGroups.ORDER_BY, entries=entries)
                facets += self._facet_group(FacetGroups.ORDER_REVERSE, entries=entries)
        return facets
