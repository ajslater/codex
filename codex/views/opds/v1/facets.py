"""OPDS v1 Facets methods."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from django.urls import reverse

from codex.models import AdminFlag
from codex.views.browser.browser import BrowserView
from codex.views.opds.const import MimeType, Rel, UserAgentNames
from codex.views.opds.util import get_user_agent_name, update_href_query_params
from codex.views.opds.v1.data import OPDS1Link
from codex.views.opds.v1.entry.data import OPDS1EntryData, OPDS1EntryObject
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.util import pop_name


@dataclass
class FacetGroup:
    """An opds:facetGroup."""

    title_prefix: str
    query_param: str
    glyph: str
    facets: tuple


@dataclass
class Facet:
    """An OPDS facet."""

    value: str
    title: str


class FacetGroups:
    """Facet Group definitions."""

    ORDER_BY = FacetGroup(
        "Order By",
        "orderBy",
        "➠",
        (
            Facet("date", "Date"),
            Facet("sort_name", "Name"),
        ),
    )
    ORDER_REVERSE = FacetGroup(
        "Order",
        "orderReverse",
        "⇕",
        (Facet("false", "Ascending"), Facet("true", "Descending")),
    )
    ALL = (ORDER_BY, ORDER_REVERSE)


class RootFacetGroups:
    """Facet Groups that only appear at the root."""

    TOP_GROUP = FacetGroup(
        "",
        "topGroup",
        "⊙",
        (
            Facet("p", "Publishers View"),
            Facet("s", "Series View"),
            Facet("f", "Folder View"),
            Facet("a", "Story Arc View"),
        ),
    )
    ALL = (TOP_GROUP,)


DEFAULT_FACETS = {
    "topGroup": "p",
    "orderBy": "sort_name",
    "orderReverse": "false",
}


class OPDS1FacetsView(BrowserView):
    """OPDS 1 Facets methods."""

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._user_agent_name: str | None = None
        self._mime_type_map: MappingProxyType[str, str] | None = None
        self._use_facets: bool | None = None
        self._obj: MappingProxyType[str, Any] | None = None

    @property
    def user_agent_name(self) -> str:
        """Memoize user agent name."""
        if self._user_agent_name is None:
            self._user_agent_name = get_user_agent_name(self.request)
        return self._user_agent_name

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

    def _facet(self, kwargs, facet_group, facet_title, new_query_params):
        kwargs = pop_name(kwargs)
        href = reverse("opds:v1:feed", kwargs=kwargs)
        facet_active = False
        for key, val in new_query_params.items():
            if self.request.GET.get(key) == val:
                facet_active = True
                break
        href = update_href_query_params(href, self.request.GET, new_query_params)

        title = " ".join(filter(None, (facet_group.title_prefix, facet_title))).strip()
        return OPDS1Link(
            Rel.FACET,
            href,
            MimeType.NAV,
            title=title,
            facet_group=facet_group.query_param,
            facet_active=facet_active,
        )

    def _facet_entry(self, item, facet_group, facet, query_params):
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
        zero_pad: int = self.obj["zero_pad"]  # type: ignore
        data = OPDS1EntryData(
            self.opds_acquisition_groups, zero_pad, False, self.mime_type_map
        )
        return OPDS1Entry(entry_obj, qps, data)

    def _is_facet_active(self, facet_group, facet):
        compare = [facet.value]
        default_val = DEFAULT_FACETS.get(facet_group.query_param)
        if facet.value == default_val:
            compare += [None]
        return self.request.GET.get(facet_group.query_param) in compare

    @staticmethod
    def _did_special_group_change(group, facet_group):
        """Test if one of the special groups changed."""
        for test_group in ("f", "a"):
            if (
                group == test_group
                and facet_group != test_group
                or group != test_group
                and facet_group == test_group
            ):
                return True
        return False

    def _facet_or_facet_entry(self, facet_group, facet, entries):
        # This logic preempts facet:activeFacet but no one uses it.
        # don't add default facets if in default mode.
        if self._is_facet_active(facet_group, facet):
            return None

        group = self.kwargs.get("group")
        if facet_group.query_param == "topGroup" and self._did_special_group_change(
            group, facet.value
        ):
            kwargs = {"group": facet.value, "pks": {}, "page": 1}
        else:
            kwargs = self.kwargs

        qps = {facet_group.query_param: facet.value}
        if entries and self.kwargs.get("page") == 1:
            facet = self._facet_entry(kwargs, facet_group, facet, qps)
        else:
            facet = self._facet(kwargs, facet_group, facet.title, qps)
        return facet

    def _facet_group(self, facet_group, entries):
        facets = []
        for facet in facet_group.facets:
            if facet.value == "f":
                efv_flag = (
                    AdminFlag.objects.only("on")
                    .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
                    .on
                )
                if not efv_flag:
                    continue
            if facet_obj := self._facet_or_facet_entry(facet_group, facet, entries):
                facets += [facet_obj]
        return facets

    def facets(self, entries=False, root=True):
        """Return facets."""
        facets = []
        group = self.kwargs.get("group")
        add_order_facets = (
            group != "c" and self.user_agent_name not in UserAgentNames.CLIENT_REORDERS
        )
        if not add_order_facets:
            facets += self._facet_group(FacetGroups.ORDER_BY, entries)
            facets += self._facet_group(FacetGroups.ORDER_REVERSE, entries)
        if root:
            facets += self._facet_group(RootFacetGroups.TOP_GROUP, entries)
        return facets
