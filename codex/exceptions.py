"""Special Redirect Error."""

from collections.abc import Mapping
from copy import deepcopy
from pprint import pformat

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.logger.logging import get_logger
from codex.serializers.choices import DEFAULTS
from codex.serializers.route import RouteSerializer

LOG = get_logger(__name__)


class SeeOtherRedirectError(APIException):
    """Redirect for 303."""

    status_code = HTTP_303_SEE_OTHER
    default_code = "redirect"
    default_detail = "redirect to a valid route"

    def __init__(self, detail: Mapping[str, str | dict]):
        """Create a response to pass to the exception handler."""
        detail = dict(detail)
        route: dict = detail.get("route", {})  # type: ignore
        params: dict = route.get("params", DEFAULTS["breadcrumbs"][0])
        # Save route in server format for redirect reverse
        params.pop("name", None)
        self.route_kwargs = params
        # Serialize route for detail
        serializer = RouteSerializer(params)
        route = deepcopy(route)
        route["params"] = serializer.data
        detail["route"] = route
        # Pop uneccissary breadcrumbs.
        detail.get("settings", {}).pop("breadcrumbs", None)  # type: ignore
        self.detail: Mapping[str, str | Mapping] = detail  # type: ignore
        LOG.debug(f"redirect {pformat(detail)}")
        # super().__init__ converts every type into strings! do not use it.

    def _add_query_params(self, url):
        """Change OPDS settings like the frontend does with error.detail."""
        query_params = {}
        settings: Mapping = self.detail.get("settings", {})  # type: ignore
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
        url = reverse(url_name, kwargs=self.route_kwargs)
        url = self._add_query_params(url)

        return redirect(url, permanent=False)
