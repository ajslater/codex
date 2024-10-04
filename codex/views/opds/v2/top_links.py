"""OPDS v2.0 top links section methods."""

from codex.views.opds.const import MimeType, Rel
from codex.views.opds.v2.links import HrefData, LinkData, OPDS2LinksView


class OPDS2TopLinksView(OPDS2LinksView):
    """OPDS 2.0 top links section methods."""

    def _link_auth(self):
        href_data = HrefData(
            {},
            url_name="opds:authentication:v1",
            absolute_query_params=True,
        )
        link_data = LinkData(
            Rel.AUTHENTICATION,
            href_data,
            mime_type=MimeType.AUTHENTICATION,
        )
        return self.link(link_data)

    def _link_search(self):
        kwargs = {"group": "s", "pks": (0,), "page": 1}
        href_data = HrefData(kwargs, absolute_query_params=True, max_page=1)
        link_data = LinkData(Rel.SEARCH, href_data, template="{?query}")
        return self.link(link_data)

    def _get_static_links(self):
        start_href_data = HrefData(
            {}, url_name="opds:v2:start", absolute_query_params=True
        )
        start_link_data = LinkData(Rel.START, start_href_data)

        register_href_data = HrefData(
            {},
            url_name="app:start",
            absolute_query_params=True,
        )
        register_link_data = LinkData(
            Rel.REGISTER,
            register_href_data,
            mime_type=MimeType.HTML,
        )

        return (
            self._link_auth(),
            self._link_search(),
            self.link(start_link_data),
            self.link(register_link_data),
        )

    def _top_route(self):
        group = "f" if self.kwargs.get("group") == "f" else "r"
        return {"group": group, "pks": (0,), "page": 1}

    def _link_page(self, rel, page):
        """Links to a page of results."""
        kwargs = {**self.kwargs, "page": page}
        href_data = HrefData(kwargs)
        link_data = LinkData(rel, href_data)
        return self.link(link_data)

    def get_links(self, up_route):
        """Get the top links section of the feed."""
        page = self.kwargs.get("page")
        top_href_data = HrefData(self._top_route())
        top_link_data = LinkData(Rel.TOP, top_href_data)
        up_href_data = HrefData(up_route)
        up_link_data = LinkData(Rel.UP, up_href_data)
        links_data = [
            self.link_self(),
            *self._get_static_links(),
            self._link_page("first", 1),
            self._link_page("previous", page - 1),
            self._link_page("next", page + 1),
            self._link_page("last", self.num_pages),
            self.link(top_link_data),
        ]
        if up_route:
            links_data += [
                self.link(up_link_data),
            ]

        link_dict = {}
        for link in links_data:
            self.link_aggregate(link_dict, link)
        return self.get_links_from_dict(link_dict)
