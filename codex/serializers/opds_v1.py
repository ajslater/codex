"""Serializers for the browser view."""
from rest_framework.serializers import (
    CharField,
    DateField,
    DecimalField,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.browser import (
    BrowserCardSerializer,
    BrowserRouteSerializer,
    BrowserTitleSerializer,
)
from codex.serializers.mixins import (
    UNIONFIX_PREFIX,
    BrowserCardOPDSBaseSerializer,
    get_serializer_values_map,
)


# LOOK AT BROWSERCARD
class OPDSEntrySerializer(BrowserCardOPDSBaseSerializer):
    """Browse card displayed in the browser."""

    size = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "size")
    date = DateField(read_only=True, source=UNIONFIX_PREFIX + "date")
    summary = CharField(read_only=True, source=UNIONFIX_PREFIX + "summary")
    #
    # authors, category, dc:identifier SOME CVID?


BROWSER_CARD_AND_OPDS_ORDERED_UNIONFIX_VALUES_MAP = get_serializer_values_map(
    [BrowserCardSerializer, OPDSEntrySerializer]
)


class OPDSFeedSerializer(Serializer):
    """The main browse list."""

    NUM_AUTOCOMPLETE_QUERIES = 10

    browser_title = BrowserTitleSerializer(read_only=True)
    model_group = CharField(read_only=True)
    up_route = BrowserRouteSerializer(allow_null=True, read_only=True)
    obj_list = ListField(
        child=OPDSEntrySerializer(read_only=True), allow_empty=True, read_only=True
    )
    num_pages = IntegerField(read_only=True)
    issue_max = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
    )
    covers_timestamp = IntegerField(read_only=True)
