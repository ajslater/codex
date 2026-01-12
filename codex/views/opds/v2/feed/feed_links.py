"""OPDS v2.0 top links section methods."""

from codex.views.opds.const import MimeType, Rel
from codex.views.opds.v2.feed.links import LinkData, OPDS2LinksView
from codex.views.opds.v2.href import HrefData


class OPDS2FeedLinksView(OPDS2LinksView):
    """OPDS 2.0 top links section methods."""

    def _link_auth(self):
        href_data = HrefData(
            {},
            url_name="opds:auth:v1",
        )
        link_data = LinkData(
            Rel.AUTHENTICATION,
            href_data,
            mime_type=MimeType.AUTHENTICATION,
        )
        return self.link(link_data)

    def _link_search(self):
        kwargs = {"group": "s", "pks": (0,), "page": 1}
        query_params = {"q": ""}
        href_data = HrefData(kwargs, query_params=query_params, max_page=1)
        link_data = LinkData(Rel.SEARCH, href_data, template="{?query}")
        return self.link(link_data)

    def _get_static_links(self):
        start_href_data = HrefData({}, url_name="opds:v2:start")
        start_link_data = LinkData(Rel.START, start_href_data)

        register_href_data = HrefData(
            {},
            url_name="app:start",
        )
        register_link_data = LinkData(
            Rel.REGISTER,
            register_href_data,
            mime_type=MimeType.HTML,
        )

        static_links = [
            self._link_auth(),
            self._link_search(),
        ]

        static_links += [
            self.link(start_link_data),
        ]
        if not self.request.user:
            static_links += [
                self.link(register_link_data),
            ]

        return static_links

    def _top_route(self):
        group = "f" if self.kwargs.get("group") == "f" else "r"
        return {"group": group, "pks": (0,), "page": 1}

    def _link_page(self, rel, page):
        """Links to a page of results."""
        kwargs = {**self.kwargs, "page": page}
        href_data = HrefData(kwargs, inherit_query_params=True)
        link_data = LinkData(rel, href_data)
        return self.link(link_data)

    def get_links(self, up_route):
        """Get the top links section of the feed."""
        page = self.kwargs.get("page", 0)
        top_href_data = HrefData(self._top_route(), inherit_query_params=True)
        top_link_data = LinkData(Rel.TOP, top_href_data)
        up_href_data = HrefData(up_route, inherit_query_params=True)
        up_link_data = LinkData(Rel.UP, up_href_data)
        links_data = [
            self.link_self(),
            *self._get_static_links(),
        ]
        if page != 1:
            links_data += [
                self._link_page("first", 1),
            ]
        if page > 1:
            links_data += [
                self._link_page("previous", page - 1),
            ]
        if page != self.num_pages:
            links_data += [
                self._link_page("next", page + 1),
                self._link_page("last", self.num_pages),
            ]

        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if group not in {"r", "f", "a"} and 0 not in pks:
            links_data += [
                self.link(top_link_data),
                self.link(up_link_data),
            ]

        link_dict = {}
        for link in links_data:
            self.link_aggregate(link_dict, link)
        return self.get_links_from_dict(link_dict)
