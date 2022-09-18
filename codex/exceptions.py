"""Special Redirect Error."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.serializers.choices import DEFAULTS
from codex.serializers.redirect import BrowserRedirectSerializer
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class SeeOtherRedirectError(APIException):
    """Redirect for 303."""

    status_code = HTTP_303_SEE_OTHER
    default_code = "redirect"
    default_detail = "redirect to a valid route"

    def __init__(self, detail):
        """Create a response to pass to the exception handler."""
        LOG.verbose(f"redirect {detail.get('reason')}")
        serializer = BrowserRedirectSerializer(detail)
        self.detail: dict = serializer.data
        # super().__init__ converts every type into strings!
        # do not use it.

    def _add_query_params(self, url):
        """Change OPDS settings like the frontend does with error.detail."""
        query_params = {}
        settings = self.detail.get("settings", {})
        if top_group := settings.get("top_group"):
            query_params["top_group"] = top_group
        if order_by := settings.get("order_by"):
            query_params["order_by"] = order_by
        if query_params:
            url += "?" + urlencode(query_params)
        return url

    def get_response(self, url_name):
        """Return a Django Redirect Response."""
        # only used in codex_exception_handler for opds stuff
        route = self.detail.get("route", {})
        params = route.get("params", DEFAULTS["route"])
        url = reverse(url_name, kwargs=params)
        url = self._add_query_params(url)

        return redirect(url)
