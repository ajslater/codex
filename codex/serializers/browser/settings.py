"""Serializers for the browser view."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.serializers.browser.filters import BrowserSettingsFilterSerializer
from codex.serializers.choices import CHOICES, VUETIFY_NULL_CODE

VUETIFY_NULL_CODE_STR = str(VUETIFY_NULL_CODE)


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


class BrowserSettingsSerializer(Serializer):
    """Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    It is also sent to the browser as part of BrowserOpenedSerializer.
    """

    filters = BrowserSettingsFilterSerializer(required=False)
    order_by = ChoiceField(choices=tuple(CHOICES["orderBy"].keys()), required=False)
    order_reverse = BooleanField(required=False)
    q = CharField(allow_blank=True, required=False)
    query = CharField(allow_blank=True, required=False)  # OPDS 2.0
    show = BrowserSettingsShowGroupFlagsSerializer(required=False)
    twenty_four_hour_time = BooleanField(required=False)
    top_group = ChoiceField(choices=tuple(CHOICES["topGroup"].keys()), required=False)
    opds_metadata = BooleanField(required=False)
    limit = IntegerField(required=False)
