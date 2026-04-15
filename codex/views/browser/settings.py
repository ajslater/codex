"""Browser settings views."""

from collections.abc import MutableMapping

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
)
from codex.serializers.browser.settings import (
    BrowserSettingsInputSerializer,
    BrowserSettingsSerializer,
)
from codex.serializers.settings import SettingsInputSerializer
from codex.views.const import FOLDER_GROUP, GROUP_ORDER, STORY_ARC_GROUP
from codex.views.settings import (
    BROWSER_CREATE_ARGS,
    BROWSER_FILTER_ARGS,
    SettingsBaseView,
)


class BrowserSettingsBaseView(SettingsBaseView):
    """Browser settings — model config, order-by default, and reset."""

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

    def reset_browser_settings(self) -> dict:
        """Reset browser settings to model defaults and return the params dict."""
        instance: SettingsBrowser = self._get_or_create_settings(  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
            self.MODEL,
            self.CLIENT,
            self.FILTER_ARGS,
            self.CREATE_ARGS,
        )
        defaults = self.get_browser_default_params()

        # Reset direct fields
        for key in SettingsBrowser.DIRECT_KEYS:
            setattr(instance, key, defaults[key])

        # Reset show FK to default show row
        self._save_browser_show(instance, defaults["show"])
        instance.save()

        # Reset filters in-place
        self._save_browser_filters(
            instance.filters,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            defaults["filters"],
        )

        # Reset last_route in-place
        self._save_browser_last_route(
            instance.last_route,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            defaults["last_route"],
        )

        return self.browser_instance_to_dict(instance)


class BrowserSettingsView(BrowserSettingsBaseView):
    """Browser settings GET/PATCH/DELETE endpoint."""

    input_serializer_class: type[SettingsInputSerializer] = (
        BrowserSettingsInputSerializer
    )
    serializer_class: type[BaseSerializer] | None = BrowserSettingsSerializer

    # ── Validation ──────────────────────────────────────────────────

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

    def _validate_settings_get(self, validated_data, params: dict) -> dict:
        """Validate and fix settings on GET."""
        # This is a micro version of browser/validate.py
        # It would be ideal to combine them but browser validate does redirects so maybe later.
        top_group = params["top_group"]
        group = validated_data.get("group", "r") if validated_data else "r"
        self._validate_top_group(params, group, top_group)
        self.set_order_by_default(params)
        return params

    # ── HTTP methods ────────────────────────────────────────────────

    @extend_schema(parameters=[BrowserSettingsInputSerializer])
    def get(self, *args, **kwargs) -> Response:
        """Get session settings."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        only = validated_data.get("only") if validated_data else None
        params = self.load_params_from_settings(only=only)
        params = self._validate_settings_get(validated_data, params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def patch(self, *args, **kwargs) -> Response:
        """Update session settings."""
        data = self.request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data
        params = self.load_params_from_settings()
        params.update(updates)
        self.save_params_to_settings(params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=BrowserSettingsSerializer)
    def delete(self, *args, **kwargs) -> Response:
        """Reset browser settings to model defaults."""
        params = self.reset_browser_settings()
        self.set_order_by_default(params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)
