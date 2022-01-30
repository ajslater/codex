"""Special Redirect Error."""
from logging import getLogger

from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.serializers.redirect import BrowserRedirectSerializer


LOG = getLogger(__name__)


class SeeOtherRedirectError(APIException):
    """Redirect for 303."""

    status_code = HTTP_303_SEE_OTHER
    default_code = "redirect"
    default_detail = "redirect to a valid route"

    def __init__(self, detail):
        """Create a response to pass to the exception handler."""
        LOG.verbose(f"redirect {detail.get('reason')}")  # type: ignore
        serializer = BrowserRedirectSerializer(detail)
        self.detail = serializer.data
        # super().__init__ converts every type into strings!
        # do not use it.
