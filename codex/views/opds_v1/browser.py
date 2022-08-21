"""OPDS Feed Browser."""
import math

from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.syndication.views import Feed
from django.core.handlers.wsgi import WSGIRequest
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from django.utils.feedgenerator import Enclosure

from codex.exceptions import SeeOtherRedirectError
from codex.serializers.opds_v1 import OPDSFeedSerializer
from codex.settings.logging import get_logger
from codex.views.browser import BrowserView
from codex.views.browser_util import BROWSER_ROOT_KWARGS
from codex.views.opds_v1.feedgenerator import OPDSFeedGenerator
from codex.views.opds_v1.mixins import OPDSAuthenticationMixin


LOG = get_logger(__name__)


def opds_start_view(request):
    """Redirect to start view, forwarding query strings and auth."""
    url = reverse("opds:v1:browser", kwargs=BROWSER_ROOT_KWARGS)

    # Forward the query string.
    path = request.get_full_path()
    if path:
        parts = path.split("?")
        if len(parts) >= 2:
            parts[0] = url
            url = "?".join(parts)

    response = HttpResponseRedirect(url)

    # Forward authorization.
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if auth_header:
        response["HTTP_AUTHORIZATION"] = auth_header

    return response


class OPDSAcquisitionEnclosure(Enclosure):
    """OPDS enclosures specify a rel and type."""

    def __init__(self, url, length):
        """Hardcode values for this one type."""
        self.rel = "http://opds-spec.org/acquisition"
        mime_type = OPDSFeedGenerator.OPDS_AQUISITION_TYPE
        super().__init__(url, length, mime_type)


class BrowserFeed(BrowserView, Feed, OPDSAuthenticationMixin):
    """OPDS Navigation Feed."""

    feed_type = OPDSFeedGenerator
    language = "eng-US"
    OPDS_THUMBNAIL_REL = "http://opds-spec.org/image/thumbnail"
    FOLDER_VIEW_KWARGS = {"group": "f", "pk": 0, "page": 1}
    BLANK_TITLE = "Unknown"

    class UserAgents:
        """Control whether to hack in facets with nav links."""

        NO_FACET_SUPPORT = ("Panels", "Chunky")
        CLIENT_REORDERS = ("Chunky",)
        # FACET_SUPPORT = ("yar",) # kybooks 3

    ORDER_GLYPH = "↓"
    TOP_GROUP_GLYPH = "⊙"

    def _init(self, request, kwargs):
        """Initialize a bit like the api browser."""
        self.request: WSGIRequest = request
        self.kwargs = kwargs
        self._parse_params()

        # Hacks for clients that don't support facets
        user_agent = request.headers.get("User-Agent")
        self.use_facets = True
        self.skip_order_facet_hacks = False
        for prefix in self.UserAgents.NO_FACET_SUPPORT:
            if user_agent.startswith(prefix):
                self.use_facets = False
                break
        for prefix in self.UserAgents.CLIENT_REORDERS:
            if user_agent.startswith(prefix):
                self.skip_order_facet_hacks = True
                break

    def __call__(self, request, *args, **kwargs):
        """Check permissions, use call() instead of get()."""
        response = self._authenticate(request)
        if response:
            return response

        try:
            self._init(request, kwargs)
            return super().__call__(request, *args, **kwargs)
        except SeeOtherRedirectError as exc:
            return exc.get_response("opds:v1:browser")

    def get_object(self, request, *args, **kwargs):
        """Get the main feed object from BrowserView."""
        browser_page = self._get_browser_page()
        serializer = OPDSFeedSerializer(browser_page)
        self.obj = serializer.data
        return self.obj

    def title(self, obj):
        """Create the feed title."""
        browser_title = obj.get("browser_title")
        parent_name = browser_title.get("parent_name", "All")
        if not parent_name and self.kwargs.get("pk") == 0:
            parent_name = "All"
        group_name = browser_title.get("group_name")
        names = []
        for name in (parent_name, group_name):
            if name:
                names.append(name)

        result = " ".join(names).strip()
        if not result:
            result = self.BLANK_TITLE
        return result

    def link(self):
        """Feed main link."""
        # Does not render so send it to the feed generator.
        return self.request.get_full_path()

    def description(self):
        """Feed Description."""
        return "Codex"

    def feed_guid(self):
        """Feed GUID is the uri."""
        return self.request.build_absolute_uri()

    def feed_extra_kwargs(self, obj):
        """Extra kwargs for the feed."""
        is_aq_feed = obj and obj.get("model_group") == "c"
        extra_kwargs = {
            "feed_obj": obj,
            "kwargs": self.kwargs,
            "query_params": self.request.GET.dict(),
            "self_link": self.link(),
            "is_aquisition_feed": is_aq_feed,
            "use_facets": self.use_facets,
        }
        return extra_kwargs

    def _get_facet_nav_hack_item(self, query_params, title, reverse_kwargs, glyph):
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")
        href = reverse("opds:v1:browser", kwargs=reverse_kwargs)
        return {
            "href": href,
            "name": " ".join((glyph, title)),
            "group": group,
            "pk": pk,
            "query_params": query_params,
        }

    def _get_facet_nav_hack_items(self):
        group = self.kwargs.get("group")
        order_by = self.request.GET.get("order_by")
        top_group = self.request.GET.get("top_group", "p")
        item_params = []
        if not self.skip_order_facet_hacks:
            if order_by != "date":
                item_params.append(
                    (
                        {"order_by": "date"},
                        "Order by Publication Date",
                        self.kwargs,
                        self.ORDER_GLYPH,
                    )
                )
            if order_by not in (None, "sort_name"):
                item_params.append(
                    (
                        {"order_by": "sort_name"},
                        "Order by Name",
                        self.kwargs,
                        self.ORDER_GLYPH,
                    )
                )
            if order_by != "search_score":
                item_params.append(
                    (
                        {"order_by": "search_score"},
                        "Order by Search Score",
                        self.kwargs,
                        self.ORDER_GLYPH,
                    )
                )

        browser_view_kwargs = {**self.kwargs}
        if group == "f":
            browser_view_kwargs["group"] = "r"
        if top_group != "p":
            item_params.append(
                (
                    {"top_group": "p"},
                    "Publishers View",
                    browser_view_kwargs,
                    self.TOP_GROUP_GLYPH,
                )
            )
        if top_group != "s":
            item_params.append(
                (
                    {"top_group": "s"},
                    "Series View",
                    browser_view_kwargs,
                    self.TOP_GROUP_GLYPH,
                )
            )
        if group != "f":
            item_params.append(
                (
                    {"top_group": "f"},
                    "Folder View",
                    browser_view_kwargs,
                    self.TOP_GROUP_GLYPH,
                )
            )

        items = []
        for params in item_params:
            items += [self._get_facet_nav_hack_item(*params)]
        return items

    def items(self, obj):
        """Return items from the obj."""
        items = obj.get("obj_list")
        if not self.use_facets:
            facet_items = self._get_facet_nav_hack_items()
            items = (*facet_items, *items)
        return items

    def item_link(self):
        """Link is handled by item_extra_kwargs to change its rel."""
        return ""

    @staticmethod
    def _compute_zero_pad(issue_max):
        """Compute zero padding for issues."""
        if not issue_max or issue_max < 1:
            return 1
        return math.floor(math.log10(issue_max)) + 1

    def item_title(self, item: dict):
        """Compute the item title."""
        group = item.get("group")
        parts = []
        if group == "i":
            parts.append(item.get("publisher_name"))
        elif group == "v":
            parts.append(item.get("series_name"))
        elif group == "c":
            issue_max = self.obj.get("issue_max")
            zero_pad = self._compute_zero_pad(issue_max)
            issue = item.get("issue")
            if issue is None:
                issue = Decimal(0)
            issue = issue.normalize()
            issue_suffix = item.get("issue_suffix", "")

            int_issue = math.floor(issue)
            if issue == int_issue:
                issue_str = str(int_issue)
            else:
                issue_str = str(issue)
                decimal_parts = issue_str.split(".")
                if len(decimal_parts) > 1:
                    zero_pad += len(decimal_parts[1]) + 1

            issue_num = issue_str.zfill(zero_pad)
            full_issue_str = f"#{issue_num}{issue_suffix}"
            parts.append(full_issue_str)

        parts.append(item.get("name"))

        result = " ".join(parts)
        if not result:
            result = self.BLANK_TITLE
        return result

    def item_description(self, item: dict):
        """Return a child count or comic summary."""
        # This does not render.
        # So take it's value and use it in the feed generator.
        if item.get("group") == "c":
            desc = item.get("summary")
        elif children := item.get("child_count"):
            desc = f"{children} items."
        else:
            desc = None

        return desc

    def item_guid(self, item):
        """GUID is a nav url."""
        if item.get("rel") == "alternate":
            href = item.get("href")
            if qp := item.get("query_params"):
                href += "?" + urlencode(qp)
            return href

        group = item.get("group")
        pk = item.get("pk")
        return reverse("opds:v1:browser", kwargs={"group": group, "pk": pk, "page": 1})

    def item_extra_kwargs(self, item: dict):
        """Send entry serialization to feedgenerator."""
        group = item.get("group")
        try:
            group_index = self.valid_nav_groups.index(group)
            aq_link = group_index + 1 >= len(self.valid_nav_groups)
        except (ValueError, IndexError):
            aq_link = False

        return {
            "card": item,
            "summary": self.item_description(item),
            "aq_link": aq_link,
        }
