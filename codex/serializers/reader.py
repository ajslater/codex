"""Codex Reader Serializers."""
from rest_framework.serializers import CharField, DecimalField, IntegerField, Serializer

from codex.serializers.bookmark import ComicReaderSettingsSerializer


class ComicPageRouteSerializer(Serializer):
    """A comic page route."""

    pk = IntegerField(read_only=True)
    page = IntegerField(read_only=True)


class ComicReaderBothSettingsSerializer(Serializer):
    """For both the default and local comic settings."""

    globl = ComicReaderSettingsSerializer(read_only=True)
    local = ComicReaderSettingsSerializer(read_only=True)


class ComicReaderRoutesSerializer(Serializer):
    """Previous and next comic routes."""

    prevBook = ComicPageRouteSerializer(allow_null=True, read_only=True)  # noqa: N815
    nextBook = ComicPageRouteSerializer(allow_null=True, read_only=True)  # noqa: N815


class ComicReaderTitleSerializer(Serializer):
    """Components for constructing the title."""

    seriesName = CharField(read_only=True)  # noqa: N815
    volumeName = CharField(read_only=True)  # noqa: N815
    issue = DecimalField(max_digits=5, decimal_places=1, read_only=True)
    issueCount = IntegerField(read_only=True)  # noqa: N815


class ComicReaderInfoSerializer(Serializer):
    """Information when opening a new book."""

    title = ComicReaderTitleSerializer(read_only=True)
    maxPage = IntegerField(read_only=True)  # noqa: N815
    settings = ComicReaderBothSettingsSerializer(read_only=True)
    routes = ComicReaderRoutesSerializer(read_only=True)
