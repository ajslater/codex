"""Serializers for the browser view."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.choices import BROWSER_ORDER_BY_CHOICES
from codex.serializers.browser.filters import BrowserSettingsFilterSerializer
from codex.serializers.fields import BreadcrumbsField, TimestampField, TopGroupField
from codex.serializers.route import SimpleRouteSerializer


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


class BrowserFilterChoicesInputSerilalizer(Serializer):
    """Browser Settings for the filter choices response."""

    filters = BrowserSettingsFilterSerializer(required=False)
    q = CharField(allow_blank=True, required=False)


class BrowserCoverInputSerializerBase(BrowserFilterChoicesInputSerilalizer):
    """Base Serializer for Cover and Settings."""

    custom_covers = BooleanField(required=False)
    dynamic_covers = BooleanField(required=False)
    order_by = ChoiceField(
        choices=tuple(BROWSER_ORDER_BY_CHOICES.keys()), required=False
    )
    order_reverse = BooleanField(required=False)
    show = BrowserSettingsShowGroupFlagsSerializer(required=False)


class BrowserCoverInputSerializer(BrowserCoverInputSerializerBase):
    """Browser Settings for the cover response."""

    parent = SimpleRouteSerializer(required=False)


class BrowserSettingsSerializerBase(BrowserCoverInputSerializerBase):
    """Base Serializer for Browser & OPDS Settings."""

    # search_results_limit = IntegerField(required=False)
    top_group = TopGroupField(required=False)


class OPDSSettingsSerializer(BrowserSettingsSerializerBase):
    """Browser Settings for the OPDS."""

    limit = IntegerField(required=False)
    opds_metadata = BooleanField(required=False)
    query = CharField(allow_blank=True, required=False)  # OPDS 2.0


class BrowserSettingsSerializer(BrowserSettingsSerializerBase):
    """Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    """

    breadcrumbs = BreadcrumbsField(required=False)
    mtime = TimestampField(read_only=True)
    twenty_four_hour_time = BooleanField(required=False)
