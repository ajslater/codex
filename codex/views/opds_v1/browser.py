"""OPDS Feed Browser."""
import math

from decimal import Decimal

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

    def __call__(self, request, *args, **kwargs):
        """Check permissions, use call() instead of get()."""
        response = self._authenticate(request)
        if response:
            return response

        try:
            return super().__call__(request, *args, **kwargs)
        except SeeOtherRedirectError as exc:
            return exc.get_response("opds:v1:browser")

    def get_object(self, request, *args, **kwargs):
        """Get the main feed object from BrowserView."""
        self.request: WSGIRequest = request
        self.kwargs = kwargs
        self._parse_params()
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
        extra_kwargs = {
            "feed_obj": obj,
            "kwargs": self.kwargs,
            "query_params": self.request.GET.dict(),
            "self_link": self.link(),
        }
        return extra_kwargs

    def items(self, obj):
        """Return items from the obj."""
        return obj.get("obj_list")

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
        else:
            children = item.get("child_count", "No")
            desc = f"{children} items."

        return desc

    def item_guid(self, item):
        """GUID is a nav url."""
        group = item.get("group")
        pk = item.get("pk")
        return reverse("opds:v1:browser", kwargs={"group": group, "pk": pk, "page": 0})

    def item_extra_kwargs(self, item: dict):
        """Send entry serialization to feedgenerator."""
        return {"card": item, "summary": self.item_description(item)}
