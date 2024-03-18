"""Views for browsing comic library."""

import json
from copy import deepcopy
from types import MappingProxyType
from urllib.parse import unquote_plus

from django.contrib.auth.models import User
from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize

from codex.logger.logging import get_logger
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
from codex.serializers.browser.settings import BrowserSettingsSerializer
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

    GROUP_MODEL_MAP = MappingProxyType(
        {
            GroupFilterMixin.ROOT_GROUP: None,
            "p": Publisher,
            "i": Imprint,
            "s": Series,
            "v": Volume,
            GroupFilterMixin.COMIC_GROUP: Comic,
            GroupFilterMixin.FOLDER_GROUP: Folder,
            GroupFilterMixin.STORY_ARC_GROUP: StoryArc,
        }
    )

    _GET_JSON_KEYS = frozenset({"filters", "show"})

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

    def get_query_filters_without_group(self, model, search_scores: dict):
        """Return all the filters except the group filter."""
        object_filter = self.get_group_acl_filter(model)
        object_filter &= self.get_search_filter(model, search_scores)
        object_filter &= self.get_bookmark_filter(model)
        object_filter &= self.get_comic_field_filter(self.rel_prefix)
        return object_filter

    def get_query_filters(self, model, search_scores: dict, choices=False):
        """Return the main object filter and the one for aggregates."""
        object_filter = self.get_query_filters_without_group(model, search_scores)
        object_filter &= self.get_group_filter(choices)
        return object_filter

    def _parse_query_params(self, query_params):
        """Parse GET query parameters: filter object & snake case."""
        result = {}
        for key, val in query_params.items():
            if key in self._GET_JSON_KEYS:
                unquoted_val = unquote_plus(val)  # for pocketbooks reader
                parsed_val = json.loads(unquoted_val)
                if not parsed_val:
                    continue
            else:
                parsed_val = val

            result[key] = parsed_val
        return underscoreize(result, **api_settings.JSON_UNDERSCOREIZE)

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        self.params = deepcopy(dict(self.SESSION_DEFAULTS))
        if self.request.method == "GET":
            data = self._parse_query_params(self.request.GET)
        elif hasattr(self.request, "data"):
            data = self._parse_query_params(self.request.data)
        else:
            return

        serializer = self.input_serializer_class(data=data)

        serializer.is_valid(raise_exception=True)
        self.params.update(serializer.validated_data)

    def set_rel_prefix(self, model):
        """Set the relation prefix for most fields."""
        self.rel_prefix = self.get_rel_prefix(model)
