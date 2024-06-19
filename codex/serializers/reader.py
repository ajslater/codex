"""Codex Reader Serializers."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.models import Bookmark
from codex.serializers.browser.settings import (
    BrowserSettingsFilterSerializer,
    BrowserSettingsShowGroupFlagsSerializer,
)
from codex.serializers.fields import BreadcrumbsField, TimestampField, TopGroupField
from codex.serializers.route import RouteSerializer, SimpleRouteSerializer


class ReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fit_to = ChoiceField(
        choices=Bookmark.FitTo.values,
        allow_blank=True,
        required=False,
    )
    two_pages = BooleanField(allow_null=True, required=False)
    reading_direction = CharField(allow_null=True, required=False)
    read_rtl_in_reverse = BooleanField(allow_null=True, required=False)
    finish_on_last_page = BooleanField(allow_null=True, required=False)
    mtime = TimestampField(read_only=True)


class ReaderComicSerializer(Serializer):
    """Prev, Next and Current Comic info."""

    pk = IntegerField(read_only=True)
    settings = ReaderSettingsSerializer(read_only=True)
    max_page = IntegerField(read_only=True)
    reading_direction = CharField(read_only=True)
    mtime = TimestampField(read_only=True)


class ReaderArcSerializer(SimpleRouteSerializer):
    """Information about the current Arc."""

    count = IntegerField(required=False)
    index = IntegerField(required=False)
    filters = BrowserSettingsFilterSerializer(required=False)
    mtime = TimestampField(read_only=True)
    name = CharField(required=False)


class ReaderViewInputSerializer(Serializer):
    """Input for the reader serailizer."""

    arc = ReaderArcSerializer(required=False)
    breadcrumbs = BreadcrumbsField(required=False)
    browser_arc = ReaderArcSerializer(required=False)
    show = BrowserSettingsShowGroupFlagsSerializer(required=False)
    top_group = TopGroupField(required=False)


class ReaderCurrentComicSerializer(ReaderComicSerializer):
    """Current comic only Serializer."""

    # For title
    series_name = CharField(read_only=True, required=False)
    volume_name = CharField(read_only=True, required=False)
    issue_number = DecimalField(
        max_digits=None,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
        required=False,
    )
    issue_suffix = CharField(read_only=True, required=False)
    issue_count = IntegerField(
        read_only=True,
        required=False,
    )

    file_type = CharField(read_only=True, required=False)
    filename = CharField(read_only=True, required=False)
    name = CharField(read_only=True, required=False)


class ReaderBooksSerializer(Serializer):
    """All comics relevant to the reader."""

    current = ReaderCurrentComicSerializer(read_only=True)
    prev_book = ReaderComicSerializer(read_only=True, required=False)
    next_book = ReaderComicSerializer(read_only=True, required=False)


class ReaderComicsSerializer(Serializer):
    """Books and arcs."""

    books = ReaderBooksSerializer(read_only=True)
    arcs = ReaderArcSerializer(many=True, read_only=True)
    arc = ReaderArcSerializer(read_only=True)
    close_route = RouteSerializer(read_only=True)
    mtime = TimestampField(read_only=True)
