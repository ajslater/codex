"""Browser session view."""

from drf_spectacular.utils import extend_schema
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.serializers.browser.settings import (
    BrowserSettingsInputSerializer,
    BrowserSettingsSerializer,
)
from codex.views.const import GROUP_ORDER
from codex.views.settings import SettingsView


class BrowserSettingsView(SettingsView):
    """Get Browser Settings."""

    input_serializer_class = BrowserSettingsInputSerializer
    # Put Browser Settings is normally done through BrowserView.get()
    serializer_class: type[BaseSerializer] | None = BrowserSettingsSerializer

    SESSION_KEY: str = SettingsView.BROWSER_SESSION_KEY

    @staticmethod
    def _validate_browse_top_group(params, group, top_group):
        """Validate top group for browse groups."""
        show = params["show"]
        if group == "r" or (
            show.get(top_group)
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
    def _validate_top_group(cls, params, group, top_group):
        """Validate top group."""
        if group == top_group:
            return

        if group in "fa":
            params["top_group"] = group
        else:
            cls._validate_browse_top_group(params, group, top_group)

    @override
    def validate_settings_get(self, validated_data, params):
        """Change bad settings."""
        # This is a micro version of browser/validate.py
        # It would be ideal to combine them but browser validate does redirects so maybe later.
        # Bookmark is also a browser view, but it's patch() doesn't actually use top group, I think.
        top_group = params["top_group"]
        group = validated_data.get("group", "r") if validated_data else "r"
        self._validate_top_group(params, group, top_group)
        return params

    @override
    @extend_schema(parameters=[BrowserSettingsInputSerializer])
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)
