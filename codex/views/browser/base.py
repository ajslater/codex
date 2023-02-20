"""Views for browsing comic library."""
import json
from copy import deepcopy
from urllib.parse import unquote_plus

from django.contrib.auth.models import User
from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize
from rest_framework.exceptions import ValidationError

from codex.logger.logging import get_logger
from codex.serializers.browser import BrowserSettingsSerializer
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.browser.filters.field import ComicFieldFilter
from codex.views.browser.filters.group import GroupFilterMixin
from codex.views.browser.filters.search import SearchFilterMixin

LOG = get_logger(__name__)


class BrowserBaseView(
    ComicFieldFilter, BookmarkFilterMixin, GroupFilterMixin, SearchFilterMixin
):
    """Browse comics with a variety of filters and sorts."""

    input_serializer_class = BrowserSettingsSerializer

    _GET_JSON_KEYS = frozenset(("filters", "show"))

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._is_admin = None
        self.params = {}

    def is_admin(self):
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user
            self._is_admin = user and isinstance(user, User) and user.is_staff
        return self._is_admin

    def get_query_filters_without_group(self, is_model_comic):
        """Return all the filters except the group filter."""
        object_filter = self.get_group_acl_filter(is_model_comic)

        search_filter, search_scores = self.get_search_filter(is_model_comic)
        object_filter &= search_filter
        object_filter &= self.get_bookmark_filter(is_model_comic, None)
        object_filter &= self.get_comic_field_filter(is_model_comic)
        return object_filter, search_scores

    def get_query_filters(self, is_model_comic, choices=False):
        """Return the main object filter and the one for aggregates."""
        (
            object_filter,
            search_scores,
        ) = self.get_query_filters_without_group(is_model_comic)

        object_filter &= self.get_group_filter(choices)

        return object_filter, search_scores

    def _parse_query_params(self, query_params):
        """Parse GET query parameters: filter object & snake case."""
        result = {}
        for key, val in query_params.items():
            if key in self._GET_JSON_KEYS:
                val = unquote_plus(val)  # for pocketbooks reader
                parsed_val = json.loads(val)
                if not parsed_val:
                    continue
            else:
                parsed_val = val

            result[key] = parsed_val
        result = underscoreize(result, **api_settings.JSON_UNDERSCOREIZE)

        return result

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        self.params = deepcopy(self.SESSION_DEFAULTS)
        if self.request.method == "GET":
            data = self._parse_query_params(self.request.GET)
        elif hasattr(self.request, "data"):
            data = self._parse_query_params(self.request.data)
        else:
            return

        serializer = self.input_serializer_class(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            LOG.error(serializer.errors)
            raise exc
        self.params.update(serializer.validated_data)
