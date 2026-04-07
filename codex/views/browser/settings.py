"""Browser session view."""

from collections.abc import MutableMapping
from typing import override

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models.settings import ClientChoices, SettingsBrowser
from codex.serializers.browser.settings import (
    BrowserSettingsInputSerializer,
    BrowserSettingsSerializer,
)
from codex.views.const import FOLDER_GROUP, GROUP_ORDER, STORY_ARC_GROUP
from codex.views.settings.base import (
    SettingsReadView,
    SettingsWriteView,
)
from codex.views.settings.const import BROWSER_CREATE_ARGS, BROWSER_FILTER_ARGS
from codex.views.settings.settings import SettingsView


class BrowserSettingsReadView(SettingsReadView):
    """Browser settings configuration (read-only)."""

    MODEL = SettingsBrowser
    CLIENT = ClientChoices.API
    FILTER_ARGS = BROWSER_FILTER_ARGS
    CREATE_ARGS = BROWSER_CREATE_ARGS

    def set_order_by_default(self, params: MutableMapping) -> None:
        """Set dynamic default for null order_by by group."""
        if params["order_by"]:
            return
        group = self.kwargs.get("group")
        order_by = (
            "filename"
            if group == FOLDER_GROUP
            else "story_arc_number"
            if group == STORY_ARC_GROUP
            else "sort_name"
        )
        params["order_by"] = order_by


class BrowserSettingsView(BrowserSettingsReadView, SettingsView):
    """Get Browser Settings."""

    input_serializer_class = BrowserSettingsInputSerializer
    # Put Browser Settings is normally done through BrowserView.get()
    serializer_class: type[BaseSerializer] | None = BrowserSettingsSerializer

    @staticmethod
    def _validate_browse_top_group(params, group: str, top_group: str) -> None:
        """Validate top group for browse groups."""
        show = params["show"]
        if group == "r" or (
            group in GROUP_ORDER
            and show.get(top_group)
            and GROUP_ORDER.index(top_group) < GROUP_ORDER.index(group)
        ):
            return

        for show_group, on in show.items():
            if on:
                params["top_group"] = show_group
                break
        else:
            params["top_group"] = "c"

    @classmethod
    def _validate_top_group(cls, params, group: str, top_group: str) -> None:
        """Validate top group."""
        if group == top_group:
            return

        if group in "fa":
            params["top_group"] = group
        else:
            cls._validate_browse_top_group(params, group, top_group)

    @override
    def validate_settings_get(self, validated_data, params) -> dict:
        """Change bad settings."""
        # This is a micro version of browser/validate.py
        # It would be ideal to combine them but browser validate does redirects so maybe later.
        top_group = params["top_group"]
        group = validated_data.get("group", "r") if validated_data else "r"
        self._validate_top_group(params, group, top_group)
        self.set_order_by_default(params)
        return params

    @override
    @extend_schema(parameters=[BrowserSettingsInputSerializer])
    def get(self, *args, **kwargs) -> Response:
        return super().get(*args, **kwargs)


class BrowserSettingsWriteView(BrowserSettingsReadView, SettingsWriteView):
    """Browser settings with full mutation support."""
