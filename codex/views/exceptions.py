"""Special Redirect Error."""

from collections.abc import Mapping
from copy import deepcopy
from pprint import pformat

from caseconverter import camelcase
from django.core.validators import EMPTY_VALUES
from django.shortcuts import redirect
from django.urls import reverse
from loguru import logger
from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_303_SEE_OTHER

from codex.choices.browser import DEFAULT_BROWSER_ROUTE
from codex.serializers.fields.browser import BreadcrumbsField
from codex.serializers.route import RouteSerializer
from codex.views.util import pop_name

_OPDS_REDIRECT_SETTINGS_KEYS = ("order_by", "top_group", "orderBy", "topGroup")
_REDIRECT_SETTINGS_KEYS = ("breadcrumbs", *_OPDS_REDIRECT_SETTINGS_KEYS)


class SeeOtherRedirectError(APIException):
    """Redirect for 303."""

    status_code = HTTP_303_SEE_OTHER
    default_code = "redirect"
    default_detail = "redirect to a valid route"

    def __init__(self, detail):
        """Create a response to pass to the exception handler."""
        super().__init__(detail)
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
            filtered_settings[camelcase(key)] = value
        detail["settings"] = filtered_settings

        self.detail = detail

        logger.debug(f"redirect {pformat(self.detail)}")

    def _get_query_params(self):
        """Change OPDS settings like the frontend does with error.detail."""
        query_params = {}
        settings = (
            self.detail.get("settings", {}) if isinstance(self.detail, Mapping) else {}  # ty: ignore[no-matching-overload]
        )
        for key in _OPDS_REDIRECT_SETTINGS_KEYS:
            value = settings.get(key)
            if value not in EMPTY_VALUES:
                query_params[key] = value
        return query_params

    def get_response(self, url_name):
        """Return a Django Redirect Response."""
        # only used in codex_exception_handler for opds stuff
        query = self._get_query_params()
        url = reverse(url_name, kwargs=self.route_kwargs, query=query)
        return redirect(url, permanent=False)
