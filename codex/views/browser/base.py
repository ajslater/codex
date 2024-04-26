"""Views for browsing comic library."""

import json
from copy import deepcopy
from types import MappingProxyType
from typing import Any
from urllib.parse import unquote_plus

from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.aggregates import Max, Min
from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize
from rest_framework.exceptions import NotFound

from codex.logger.logging import get_logger
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
from codex.models.groups import BrowserGroupModel
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

    GROUP_MODEL_MAP: MappingProxyType[str, type[BrowserGroupModel] | None] = (
        MappingProxyType(
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
    )
    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType({})

    _GET_JSON_KEYS = frozenset({"filters", "show"})
    TARGET = ""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._is_admin: bool = False
        self.params: MappingProxyType[str, Any] = MappingProxyType({})
        self.bm_annotation_data = {}
        self.rel_prefix: str = ""
        self.model: type[BrowserGroupModel] | None = None
        self.group_class: type[BrowserGroupModel] | None = None
        self.model_group: str = ""
        self.is_model_comic: bool = False
        self.admin_flags: MappingProxyType[str, bool] = MappingProxyType({})
        self.order_agg_func: type[Min | Max] = Min

    def is_admin(self):
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user
            self._is_admin = user and isinstance(user, User) and user.is_staff
        return self._is_admin

    def set_admin_flags(self):
        """Set browser relevant admin flags."""
        admin_pairs = AdminFlag.objects.filter(
            key__in=self.ADMIN_FLAG_VALUE_KEY_MAP.keys()
        ).values_list("key", "on")
        admin_flags = {}
        for key, on in admin_pairs:
            export_key = self.ADMIN_FLAG_VALUE_KEY_MAP[key]
            admin_flags[export_key] = on
        self.admin_flags = MappingProxyType(admin_flags)

    def get_model_group(self):
        """Determine model group for set_browse_model()."""
        group = self.kwargs["group"]
        if group == self.ROOT_GROUP:
            group = self.params["top_group"]
        return group

    def get_query_filters_without_group(self, model, cover=False):
        """Return all the filters except the group filter."""
        add_acl = not (cover and self.model == Folder)  # type: ignore
        object_filter = self.get_group_acl_filter(model) if add_acl else Q()
        object_filter &= self.get_bookmark_filter(model)
        object_filter &= self.get_comic_field_filter(self.rel_prefix)
        return object_filter

    def get_query_filters(self, model, choices=False):
        """Return the main object filter and the one for aggregates."""
        object_filter = self.get_query_filters_without_group(model)
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
                parsed_key = key
            elif key in ("q", "query"):
                # parse and strip query param
                # "query" is used by opds v2
                if "q" in result:
                    continue
                parsed_val = val.strip()
                if not parsed_val:
                    continue
                parsed_key = "q"
            else:
                parsed_key = key
                parsed_val = val

            result[parsed_key] = parsed_val
        return underscoreize(result, **api_settings.JSON_UNDERSCOREIZE)

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        if self.request.method == "GET":
            data = self._parse_query_params(self.request.GET)
        elif hasattr(self.request, "data"):
            data = self._parse_query_params(self.request.data)
        else:
            data = {}

        serializer = self.input_serializer_class(data=data)

        serializer.is_valid(raise_exception=True)
        params = deepcopy(dict(self.SESSION_DEFAULTS))
        params.update(serializer.validated_data)
        self.params = MappingProxyType(params)

    def set_order_key(self):
        """Unused until browser."""

    def validate_settings(self):
        """Unused until browser."""

    def set_model(self):
        """Set the model for the browse list."""
        group = self.kwargs["group"]
        self.group_class = self.GROUP_MODEL_MAP[group]

        self.model_group = self.get_model_group()
        self.model = self.GROUP_MODEL_MAP.get(self.model_group)
        if self.model is None:
            detail = f"Cannot browse {group=}"
            LOG.debug(detail)
            raise NotFound(detail=detail)
        self.is_model_comic = self.model == Comic

    def set_rel_prefix(self):
        """Set the relation prefix for most fields."""
        self.rel_prefix = self.get_rel_prefix(self.model)

    def init_request(self):
        """Initialize request."""
        self.set_admin_flags()
        self.parse_params()
        self.set_order_key()
        self.validate_settings()
        self.set_model()
        self.set_rel_prefix()
