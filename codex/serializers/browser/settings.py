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
    BROWSER_TABLE_COLUMNS,
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
from codex.views.browser.columns import coerce_columns


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

    JSON_FIELDS = frozenset(
        BrowserSettingsSerializerBase.JSON_FIELDS | {"table_columns"}
    )

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
        Reject unknown top-group keys and unknown column keys.

        Stored settings predating registry renames (e.g. ``issue_number``
        → ``issue``) are coerced to current keys before validation so
        existing data round-trips cleanly instead of 400-ing.
        """
        invalid_top_groups = set(value) - set(BROWSER_TOP_GROUP_CHOICES.keys())
        if invalid_top_groups:
            reason = f"Invalid top_group keys: {sorted(invalid_top_groups)}"
            raise ValidationError(reason)
        valid_columns = set(BROWSER_TABLE_COLUMNS.keys())
        coerced: dict[str, list[str]] = {}
        for top_group, columns in value.items():
            migrated = coerce_columns(columns)
            invalid_columns = set(migrated) - valid_columns
            if invalid_columns:
                reason = (
                    f"Invalid column keys for {top_group!r}: {sorted(invalid_columns)}"
                )
                raise ValidationError(reason)
            coerced[top_group] = migrated
        return coerced


class BrowserSettingsInputSerializer(SettingsInputSerializer):
    """Browser Set Settings Input Serializer."""

    group = BrowserRouteGroupField(required=False)


class BrowserPageInputSerializer(BrowserSettingsSerializer):
    """
    Input parser for the browse page endpoint.

    Adds the ``columns`` query param: a comma-separated list of column
    keys from the table-view registry. The browser view consumes it
    when ``view_mode == "table"`` to project rows. Each key must be a
    valid registry entry; unknown keys cause a 400.
    """

    columns = CharField(required=False, allow_blank=True)

    def validate_columns(self, value: str) -> tuple[str, ...]:
        """Split, trim, coerce-deprecated, and validate column keys."""
        if not value:
            return ()
        raw = [k.strip() for k in value.split(",") if k.strip()]
        keys = tuple(coerce_columns(raw))
        valid = set(BROWSER_TABLE_COLUMNS.keys())
        invalid = [k for k in keys if k not in valid]
        if invalid:
            reason = f"Invalid column keys: {sorted(invalid)}"
            raise ValidationError(reason)
        return keys
