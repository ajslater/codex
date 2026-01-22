"""Serializers for the browser view."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    Serializer,
)
from typing_extensions import override

from codex.choices.browser import BROWSER_ORDER_BY_CHOICES
from codex.serializers.browser.filters import BrowserSettingsFilterInputSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.fields.browser import BreadcrumbsField
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


class BrowserFilterChoicesInputSerializer(JSONFieldSerializer):
    """Browser Settings for the filter choices response."""

    JSON_FIELDS: frozenset[str] = frozenset({"filters"})

    filters = BrowserSettingsFilterInputSerializer(required=False)
    # NOT Sanitized because so complex.
    q = CharField(allow_blank=True, required=False)


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
    def to_internal_value(self, data):
        if "q" not in data and (query := data.get("query")):
            # parse query param for opds v2
            data = data.copy()
            data["q"] = query
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

    JSON_FIELDS: frozenset[str] = frozenset(
        BrowserSettingsSerializerBase.JSON_FIELDS | {"breadcrumbs"}
    )

    breadcrumbs = BreadcrumbsField(required=False)
    mtime = TimestampField(read_only=True)
    twenty_four_hour_time = BooleanField(required=False)
    always_show_filename = BooleanField(required=False)


class BrowserSettingsInputSerializer(SettingsInputSerializer):
    """Browser Set Settings Input Serializer."""

    group = BrowserRouteGroupField(required=False)
