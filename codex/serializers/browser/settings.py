"""Serializers for the browser view."""

from typing import override

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    IntegerField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.choices.browser import (
    BROWSER_ORDER_BY_CHOICES,
    BROWSER_TABLE_COVER_SIZE_CHOICES,
    BROWSER_TOP_GROUP_CHOICES,
    BROWSER_VIEW_MODE_CHOICES,
)
from codex.serializers.browser.filters import BrowserSettingsFilterInputSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.fields.group import BrowseGroupField, BrowserRouteGroupField
from codex.serializers.mixins import JSONFieldSerializer
from codex.serializers.route import SimpleRouteSerializer
from codex.serializers.settings import SettingsInputSerializer


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


class BrowserSettingsLastRouteSerializer(Serializer):
    """Last route for browser settings output."""

    group = CharField()
    pks = CharField()
    page = IntegerField()

    @override
    def to_representation(self, instance) -> dict:
        """Handle both dicts and SettingsBrowserLastRoute model instances."""
        if not isinstance(instance, dict):
            # Model instance
            pks = instance.pks
            instance = {
                "group": instance.group,
                "pks": tuple(pks) if pks else (0,),
                "page": instance.page,
            }
        return instance


class BrowserFilterChoicesInputSerializer(JSONFieldSerializer):
    """Browser Settings for the filter choices response."""

    JSON_FIELDS: frozenset[str] = frozenset({"filters"})

    filters = BrowserSettingsFilterInputSerializer(required=False)
    # NOT Sanitized because so complex.
    search = CharField(allow_blank=True, required=False)


class BrowserCoverInputSerializerBase(BrowserFilterChoicesInputSerializer):
    """Base Serializer for Cover and Settings."""

    JSON_FIELDS = frozenset(BrowserFilterChoicesInputSerializer.JSON_FIELDS | {"show"})

    custom_covers = BooleanField(required=False)
    dynamic_covers = BooleanField(required=False)
    order_by = ChoiceField(
        choices=tuple(BROWSER_ORDER_BY_CHOICES.keys()), required=False
    )
    order_reverse = BooleanField(required=False)
    show = BrowserSettingsShowGroupFlagsSerializer(required=False)


class BrowserCoverInputSerializer(BrowserCoverInputSerializerBase):
    """Browser Settings for the cover response."""

    JSON_FIELDS = frozenset(
        BrowserCoverInputSerializerBase.JSON_FIELDS | {"parent_route"}
    )

    parent_route = SimpleRouteSerializer(required=False)


class BrowserSettingsSerializerBase(BrowserCoverInputSerializerBase):
    """Base Serializer for Browser & OPDS Settings."""

    top_group = BrowseGroupField(required=False)

    @override
    def to_internal_value(self, data) -> dict:
        if "search" not in data and (search := data.get("query", data.get("q"))):
            # Accept "query" or "q" as an alias for "search".
            data = data.copy()
            data["search"] = search
        return super().to_internal_value(data)


class OPDSSettingsSerializer(BrowserSettingsSerializerBase):
    """Browser Settings for the OPDS."""

    limit = IntegerField(required=False)
    opds_metadata = BooleanField(required=False)
    query = CharField(allow_blank=True, required=False)  # OPDS 2.0


class BrowserSettingsSerializer(BrowserSettingsSerializerBase):
    """
    Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    """

    mtime = TimestampField(read_only=True)
    twenty_four_hour_time = BooleanField(required=False)
    always_show_filename = BooleanField(required=False)
    view_mode = ChoiceField(
        choices=tuple(BROWSER_VIEW_MODE_CHOICES.keys()), required=False
    )
    table_columns = DictField(
        child=ListField(child=CharField(), allow_empty=True),
        required=False,
        allow_empty=True,
    )
    table_cover_size = ChoiceField(
        choices=tuple(BROWSER_TABLE_COVER_SIZE_CHOICES.keys()), required=False
    )

    def validate_table_columns(self, value):
        """
        Reject keys that aren't valid top-groups.

        Column-key validation against the registry lives in the next step.
        """
        invalid = set(value) - set(BROWSER_TOP_GROUP_CHOICES.keys())
        if invalid:
            reason = f"Invalid top_group keys: {sorted(invalid)}"
            raise ValidationError(reason)
        return value


class BrowserSettingsInputSerializer(SettingsInputSerializer):
    """Browser Set Settings Input Serializer."""

    group = BrowserRouteGroupField(required=False)
