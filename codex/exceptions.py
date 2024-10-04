"""Special Redirect Error."""

from copy import deepcopy
from pprint import pformat
from typing import TYPE_CHECKING

from django.core.validators import EMPTY_VALUES
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.choices import DEFAULT_BROWSER_ROUTE
from codex.logger.logging import get_logger
from codex.serializers.fields import BreadcrumbsField
from codex.serializers.route import RouteSerializer
from codex.views.util import pop_name

if TYPE_CHECKING:
    from collections.abc import Mapping


LOG = get_logger(__name__)
_OPDS_REDIRECT_SETTINGS_KEYS = ("order_by", "top_group")
_REDIRECT_SETTINGS_KEYS = ("breadcrumbs", *_OPDS_REDIRECT_SETTINGS_KEYS)


class SeeOtherRedirectError(APIException):
    """Redirect for 303."""

    status_code = HTTP_303_SEE_OTHER
    default_code = "redirect"
    default_detail = "redirect to a valid route"

    def __init__(self, detail):
        """Create a response to pass to the exception handler."""
        # Copy to edit and not write over refs
        detail = dict(detail)

        # Get route params
        route = detail.get("route", {})
        params = route.get("params", DEFAULT_BROWSER_ROUTE)
        params = pop_name(params)
        route = deepcopy(route)
        route["params"] = params

        # For OPDS
        self.route_kwargs = params

        serializer = RouteSerializer(params)
        route["params"] = serializer.data
        detail["route"] = route

        filtered_settings = {}
        settings = detail.get("settings", {})
        for key in _REDIRECT_SETTINGS_KEYS:
            value = settings.get(key)
            if value in EMPTY_VALUES:
                continue
            if key == "breadcrumbs":
                value = BreadcrumbsField().to_representation(value)
            filtered_settings[key] = value
        detail["settings"] = filtered_settings

        self.detail = detail

        LOG.debug(f"redirect {pformat(self.detail)}")
        # super().__init__ converts every type into strings! do not use it.

    def _add_query_params(self, url):
        """Change OPDS settings like the frontend does with error.detail."""
        query_params = {}
        settings: Mapping = self.detail.get("settings", {})  # type: ignore
        for key in _OPDS_REDIRECT_SETTINGS_KEYS:
            value = settings.get(key)
            if value not in EMPTY_VALUES:
                query_params[key] = value
        if query_params:
            url += "?" + urlencode(query_params)
        return url

    def get_response(self, url_name):
        """Return a Django Redirect Response."""
        # only used in codex_exception_handler for opds stuff
        url = reverse(url_name, kwargs=self.route_kwargs)
        url = self._add_query_params(url)

        return redirect(url, permanent=False)
