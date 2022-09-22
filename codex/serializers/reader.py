"""Codex Reader Serializers."""
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.serializers.choices import CHOICES


FIT_TO_CHOICES = tuple(CHOICES["fitTo"].keys())


class PageRouteSerializer(Serializer):
    """A comic page route."""

    pk = IntegerField(read_only=True)
    page = IntegerField(read_only=True)


class ReaderRoutesSerializer(Serializer):
    """Previous and next comic routes."""

    prev_book = PageRouteSerializer(allow_null=True, read_only=True)
    next_book = PageRouteSerializer(allow_null=True, read_only=True)
    series_index = IntegerField(read_only=True)
    series_count = IntegerField(read_only=True)


class ReaderComicSerializer(Serializer):
    """Components for constructing the title."""

    file_format = CharField(read_only=True)
    issue = DecimalField(
        max_digits=None, decimal_places=3, read_only=True, coerce_to_string=False
    )
    issue_suffix = CharField(read_only=True)
    issue_count = IntegerField(read_only=True)
    max_page = IntegerField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)


class ReaderInfoSerializer(Serializer):
    """Information when opening a new book."""

    comic = ReaderComicSerializer(read_only=True)
    routes = ReaderRoutesSerializer(read_only=True)


class ReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fit_to = ChoiceField(
        choices=FIT_TO_CHOICES,
        allow_null=True,
        required=False,
    )
    two_pages = BooleanField(allow_null=True, required=False)
