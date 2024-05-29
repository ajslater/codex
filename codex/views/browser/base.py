"""Views for browsing comic library."""

from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.aggregates import Max, Min
from rest_framework.exceptions import NotFound

from codex.logger.logging import get_logger
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
)
from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.browser.filters.field import ComicFieldFilter
from codex.views.browser.filters.group import GroupFilterMixin
from codex.views.browser.filters.search import SearchFilterMixin
from codex.views.const import GROUP_MODEL_MAP, ROOT_GROUP
from codex.views.utils import reparse_json_query_params

LOG = get_logger(__name__)

if TYPE_CHECKING:
    from codex.models.groups import BrowserGroupModel

REPARSE_JSON_FIELDS = frozenset({"filters", "show"})


class BrowserBaseView(
    ComicFieldFilter, BookmarkFilterMixin, GroupFilterMixin, SearchFilterMixin
):
    """Browse comics with a variety of filters and sorts."""

    input_serializer_class = BrowserSettingsSerializer

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
        if group == ROOT_GROUP:
            group = self.params["top_group"]
        return group

    def get_query_filters_without_group(self, model, cover=False):
        """Return all the filters except the group filter."""
        add_acl = not (cover and self.model == Folder)  # type: ignore
        object_filter = self.get_group_acl_filter(model) if add_acl else Q()
        object_filter &= self.get_bookmark_filter(model)
        object_filter &= self.get_comic_field_filter(model)
        return object_filter

    def get_query_filters(self, model, choices=False):
        """Return the main object filter and the one for aggregates."""
        object_filter = self.get_query_filters_without_group(model)
        object_filter &= self.get_group_filter(choices)
        return object_filter

    def _parse_query_params(self):
        """Parse GET query parameters: filter object & snake case."""
        query_params = reparse_json_query_params(self.request.GET, REPARSE_JSON_FIELDS)
        if "q" not in query_params and (query := query_params.get("query")):
            # parse query param for opds v2
            query_params["q"] = query
        return query_params

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        data = self._parse_query_params()
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        params = deepcopy(self.request.session[self.SESSION_KEY])
        params.update(serializer.validated_data)
        self.params = MappingProxyType(params)

        self.is_bookmark_filtered = bool(self.params.get("filters", {}).get("bookmark"))

    def set_order_key(self):
        """Unused until browser."""

    def validate_settings(self):
        """Unused until browser."""

    def set_model(self):
        """Set the model for the browse list."""
        group = self.kwargs["group"]
        self.group_class = GROUP_MODEL_MAP[group]

        self.model_group = self.get_model_group()
        self.model = GROUP_MODEL_MAP.get(self.model_group)
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
