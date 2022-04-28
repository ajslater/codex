"""Codex Reader Serializers."""
from rest_framework.serializers import (
    CharField,
    DecimalField,
    IntegerField,
    JSONField,
    Serializer,
)


class ComicPageRouteSerializer(Serializer):
    """A comic page route."""

    pk = IntegerField(read_only=True)
    page = IntegerField(read_only=True)


class ComicReaderRoutesSerializer(Serializer):
    """Previous and next comic routes."""

    prev_book = ComicPageRouteSerializer(allow_null=True, read_only=True)
    next_book = ComicPageRouteSerializer(allow_null=True, read_only=True)


class ComicReaderComicSerializer(Serializer):
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


class ComicReaderInfoSerializer(Serializer):
    """Information when opening a new book."""

    comic = ComicReaderComicSerializer(read_only=True)
    routes = ComicReaderRoutesSerializer(read_only=True)
    browser_route = JSONField(read_only=True)
