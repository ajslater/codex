"""OPDS 1 Facets methods."""
from django.urls import reverse

from codex.views.browser.browser import BrowserView
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.const import (
    DEFAULT_FACETS,
    Facet,
    FacetGroups,
    OPDSLink,
    RootFacetGroups,
)
from codex.views.opds.v1.entry import OPDS1Entry, OPDS1EntryObject


class FacetsMixin(BrowserView):
    """OPDS 1 Facets methods."""

    # Overwritten by get_object()
    use_facets = False
    skip_order_facets = False
    acquisition_groups = frozenset()
    obj = {}

    def _facet(self, kwargs, facet_group, facet_title, new_query_params):
        href = reverse("opds:v1:feed", kwargs=kwargs)
        facet_active = False
        for key, val in new_query_params.items():
            if self.request.query_params.get(key) == val:
                facet_active = True
                break
        href = update_href_query_params(
            href, self.request.query_params, new_query_params
        )

        title = " ".join(filter(None, (facet_group.title_prefix, facet_title))).strip()
        return OPDSLink(
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
            pk=item.get("pk"),
            name=name,
        )
        issue_max = self.obj.get("issue_max")
        data = (self.acquisition_groups, issue_max, False)
        qps = {**self.request.query_params}
        qps.update(query_params)
        return OPDS1Entry(entry_obj, qps, data)

    def _is_facet_active(self, facet_group, facet):
        compare = [facet.value]
        default_val = DEFAULT_FACETS.get(facet_group.query_param)
        if facet.value == default_val:
            compare += [None]
        return self.request.query_params.get(facet_group.query_param) in compare

    def _facet_or_facet_entry(self, facet_group, facet, entries):
        # This logic preempts facet:activeFacet but no one uses it.
        # don't add default facets if in default mode.
        if self._is_facet_active(facet_group, facet):
            return None

        group = self.kwargs.get("group")
        if (
            facet_group.query_param == "topGroup"
            and (group == "f" and facet.value != "f")
            or (group != "f" and facet.value == "f")
        ):
            kwargs = {"group": facet.value, "pk": 0, "page": 1}
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
            if facet_obj := self._facet_or_facet_entry(facet_group, facet, entries):
                facets += [facet_obj]
        return facets

    def facets(self, entries=False, root=True):
        """Return facets."""
        facets = []
        if not self.skip_order_facets:
            facets += self._facet_group(FacetGroups.ORDER_BY, entries)
            facets += self._facet_group(FacetGroups.ORDER_REVERSE, entries)
        if root:
            facets += self._facet_group(RootFacetGroups.TOP_GROUP, entries)
            if facet_obj := self._facet_or_facet_entry(
                RootFacetGroups.TOP_GROUP, Facet("f", "Folder View"), entries
            ):
                facets += [facet_obj]
        return facets
