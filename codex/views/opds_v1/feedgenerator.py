"""OPDS Feed Generator."""
from datetime import datetime
from urllib.parse import urlencode

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.utils.encoding import iri_to_uri
from django.utils.feedgenerator import Atom1Feed, get_tag_uri, rfc3339_date
from django.utils.xmlutils import SimplerXMLGenerator

from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class OPDSFeedGenerator(Atom1Feed):
    """Generate the OPDS Browser Feed."""

    ROOT_ATTRIBUTES = {
        "xmlns:atom": "http://www.w3.org/2005/Atom",
        "xmlns:opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "xmlns:pse": "http://vaemendis.net/opds-pse/ns",
        "xmlns:dc": "http://purl.org/dc/terms/",
    }
    OPDS_THUMBNAIL_REL = "http://opds-spec.org/image/thumbnail"
    OPDS_PSE_STREAM_REL = "http://vaemendis.net/opds-pse/stream"
    OPENSEARCH_TYPE = "application/opensearchdescription+xml"
    ATOM_TYPE = "application/atom+xml"
    OPDS_CATALOG_PROFILE = "profile=opds-catalog"
    OPDS_NAV_TYPE = ";".join((ATOM_TYPE, OPDS_CATALOG_PROFILE, "kind=navigation"))
    OPDS_AQUISITION_TYPE = ";".join(
        (ATOM_TYPE, OPDS_CATALOG_PROFILE, "kind=acquisition")
    )
    OPDS_AQUISITION_REL = "http://opds-spec.org/acquisition"
    OPDS_AUTHENTICATION_TYPE = "application/opds-authentication+json"
    content_type = ";".join((ATOM_TYPE, "charset=utf-8"))
    FACET_GROUP_ORDER = "Order by"
    FACET_GROUP_TOP_GROUP = "Top Group"
    FOLDER_VIEW_KWARGS = {"group": "f", "pk": 0, "page": 1}

    def root_attributes(self):
        """Construct root attributes."""
        xmlns_opds = "http://opds-spec.org/2010/"
        if self.feed.get("feed_obj", {}).get("model_group") == "c":
            xmlns_opds += "acquisition"
        else:
            xmlns_opds += "catalog"
        attrs = {**self.ROOT_ATTRIBUTES, "xmlns:opds": xmlns_opds}
        return attrs

    def _add_query_params_to_href(self, href, include_qps, query_params_mask=None):
        """Add query params to an href."""
        if include_qps:
            query_params = {**self.feed.get("query_params", {})}
        else:
            query_params = {}

        if query_params_mask:
            query_params.update(query_params_mask)

        if query_params:
            href += "?" + urlencode(query_params)

        return href

    def _add_root_link(
        self,
        handler,
        href,
        rel,
        type,
        title=None,
        include_qps=False,
        query_params_mask=None,
        facet_group=None,
    ):
        """Add a root link."""
        href = self._add_query_params_to_href(href, include_qps, query_params_mask)
        attrs = {"href": href, "rel": rel, "type": type}
        if title:
            attrs["title"] = title
        active_facet = False
        if query_params_mask:
            active_facet = True
            all_query_params = self.feed.get("query_params", {})
            for key, val in query_params_mask.items():
                if all_query_params.get(key) != val:
                    active_facet = False
                    break
        if active_facet:
            attrs["opds:activeFacet"] = "true"
        if facet_group:
            attrs["opds:facetGroup"] = facet_group
        handler.addQuickElement("link", None, attrs)

    def _add_root_link_facet(self, handler, reverse_kwargs, title, facet_group, qpm):
        """Add a root facet link."""
        self._add_root_link(
            handler,
            reverse("opds:v1:browser", kwargs=reverse_kwargs),
            "http://opds-spec.org/facet",
            self.OPDS_NAV_TYPE,
            title=title,
            include_qps=True,
            query_params_mask=qpm,
            facet_group=facet_group,
        )

    def add_root_elements(self, handler: SimplerXMLGenerator):
        """Add all root elements."""
        handler.addQuickElement("id", self.feed["id"])
        # opds clients are unlikely to support svg (or even webp)
        handler.addQuickElement("icon", staticfiles_storage.url("img/logo-32.webp"))
        handler.addQuickElement("title", self.feed["title"])
        if self.feed.get("subtitle") is not None:
            handler.addQuickElement("subtitle", self.feed["subtitle"])
        handler.startElement("author", {})
        handler.addQuickElement("name", "Codex")
        handler.addQuickElement("uri", "https://github.com/ajslater/codex")
        handler.endElement("author")
        feed_obj = self.feed.get("feed_obj", {})
        updated = feed_obj.get("covers_timestamp")
        if updated:
            updated = datetime.fromtimestamp(updated)
            handler.addQuickElement("updated", rfc3339_date(updated))

        self._add_root_link(
            handler, self.feed.get("self_link"), "self", self.OPDS_NAV_TYPE
        )
        self._add_root_link(
            handler, reverse("opds:v1:start"), "start", self.OPDS_NAV_TYPE
        )
        self._add_root_link(
            handler,
            reverse("opds:v1:authentication"),
            "http://opds-spec.org/auth/document",
            self.OPDS_AUTHENTICATION_TYPE,
        )
        up_kwargs = feed_obj.get("up_route")
        if up_kwargs:
            self._add_root_link(
                handler,
                reverse("opds:v1:browser", kwargs=up_kwargs),
                "up",
                self.OPDS_NAV_TYPE,
            )
        kwargs = self.feed.get("kwargs", {})
        page = kwargs.get("page")
        if page is not None and page > 1:
            prev_kwargs = {**kwargs}
            prev_kwargs["page"] = page - 1
            self._add_root_link(
                handler,
                reverse("opds:v1:browser", kwargs=prev_kwargs),
                "prev",
                self.OPDS_NAV_TYPE,
            )
        if page is not None and page < feed_obj.get("num_pages"):
            next_kwargs = {**kwargs}
            next_kwargs["page"] = page + 1
            self._add_root_link(
                handler,
                reverse("opds:v1:browser", kwargs=next_kwargs),
                "next",
                self.OPDS_NAV_TYPE,
            )
        self._add_root_link(
            handler, reverse("opds:v1:opensearch"), "search", self.OPENSEARCH_TYPE
        )

        # Facet Links
        self._add_root_link_facet(
            handler,
            kwargs,
            "Order by Publication Date",
            self.FACET_GROUP_ORDER,
            {"order_by": "date"},
        )
        self._add_root_link_facet(
            handler,
            kwargs,
            "Order by Name",
            self.FACET_GROUP_ORDER,
            {"order_by": "sort_name"},
        )
        self._add_root_link_facet(
            handler,
            kwargs,
            "Order by Search Score",
            self.FACET_GROUP_ORDER,
            {"order_by": "search_score"},
        )
        browser_view_kwargs = {**kwargs}
        group = kwargs.get("group")
        if group == "f":
            browser_view_kwargs["group"] = "r"
        self._add_root_link_facet(
            handler,
            browser_view_kwargs,
            "Publishers View",
            self.FACET_GROUP_TOP_GROUP,
            {"top_group": "p"},
        )
        self._add_root_link_facet(
            handler,
            browser_view_kwargs,
            "Series View",
            self.FACET_GROUP_TOP_GROUP,
            {"top_group": "s"},
        )
        self._add_root_link_facet(
            handler,
            self.FOLDER_VIEW_KWARGS,
            "Folder View",
            self.FACET_GROUP_TOP_GROUP,
            {"top_group": "f"},
        )

    def _add_item_link(
        self,
        handler: SimplerXMLGenerator,
        rel,
        mime_type,
        href=None,
        item=None,
        key=None,
        title=None,
        length=None,
        pse_count=None,
        pse_last_read=None,
    ):
        """Add an item nav or pse link."""
        if href is None:
            if key is None or item is None:
                return
            href = item.get(key)
            if href is None:
                return
        if pse_count is None:
            href = iri_to_uri(href)
        kwargs = {
            "href": href,
            "rel": rel,
            "type": mime_type,
        }
        if length is not None:
            kwargs["length"] = length
        if title:
            kwargs["title"] = title
        if pse_count:
            kwargs["pse:count"] = pse_count
        if pse_last_read:
            kwargs["pse:lastRead"] = str(pse_last_read)
        handler.addQuickElement("link", None, kwargs)

    def add_item_elements(self, handler: SimplerXMLGenerator, item):
        """Add the item elements."""
        # Unique ID.
        if item["unique_id"] is not None:
            unique_id = item["unique_id"]
        else:
            unique_id = get_tag_uri(item["link"], item["pubdate"])
        handler.addQuickElement("id", unique_id)
        handler.addQuickElement("title", item["title"])

        # Links
        card = item.get("card", {})
        group = card.get("group")
        pk = card.get("pk")
        if group == "c":
            # PSE
            base_url = reverse("opds:v1:start")
            group_link = f"{base_url}c/{pk}/" + "{pageNumber}/p.jpg?bookmark=1"
            group_link_args = (self.OPDS_PSE_STREAM_REL, "image/jpeg")
            pse_count = str(card.get("page_count", 0))
            pse_last_read = card.get("bookmark")
            group_link_kwargs = {
                "href": group_link,
                "pse_count": pse_count,
                "pse_last_read": pse_last_read,
            }
        else:
            # Nav
            kwargs = {"group": group, "pk": pk, "page": 1}
            group_link = reverse("opds:v1:browser", kwargs=kwargs)
            group_link_args = ("subsection", self.OPDS_NAV_TYPE)
            group_link_kwargs = {
                "href": self._add_query_params_to_href(group_link, True)
            }

        self._add_item_link(handler, *group_link_args, **group_link_kwargs)

        # Thumbnail
        cover_pk = card.get("cover_pk")
        thumb_link_kwargs = {"pk": cover_pk}
        thumb_link = reverse("opds:v1:cover", kwargs=thumb_link_kwargs)
        self._add_item_link(
            handler, self.OPDS_THUMBNAIL_REL, "image/webp", href=thumb_link
        )

        # Acquistion
        if group == "c":
            download_kwargs = {"pk": pk}
            download_href = reverse("opds:v1:download", kwargs=download_kwargs)
            download_length = str(card.get("size", 0))
            self._add_item_link(
                handler,
                OPDSFeedGenerator.OPDS_AQUISITION_REL,
                OPDSFeedGenerator.OPDS_AQUISITION_TYPE,
                href=download_href,
                length=download_length,
            )

        date = card.get("date")
        if date:
            handler.addQuickElement("dc:issued", date)

        summary = item.get("summary")
        if summary:
            handler.addQuickElement("summary", summary, {"type": "text"})
