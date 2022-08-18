"""Special Redirect Error."""
from django.shortcuts import redirect
from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.serializers.redirect import BrowserRedirectSerializer
from codex.settings.logging import get_logger
from codex.views.browser_util import BROWSER_ROOT_KWARGS


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

    def get_response(self, url_name="opds:v1:browser"):
        """Return a Django Redirect Response."""
        route = self.detail.get("route", {})
        params = route.get("params", BROWSER_ROOT_KWARGS)
        return redirect(url_name, **params)
