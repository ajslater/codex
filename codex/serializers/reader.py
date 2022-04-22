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

    prevBook = ComicPageRouteSerializer(  # noqa: N815
        allow_null=True, read_only=True, source="prev_book"
    )
    nextBook = ComicPageRouteSerializer(  # noqa: N815
        allow_null=True, read_only=True, source="next_book"
    )


class ComicReaderComicSerializer(Serializer):
    """Components for constructing the title."""

    fileFormat = CharField(read_only=True, source="file_format")  # noqa N815
    issue = DecimalField(max_digits=16, decimal_places=2, read_only=True)
    issueSuffix = CharField(read_only=True, source="issue_suffix")  # noqa: N815
    issueCount = IntegerField(read_only=True, source="issue_count")  # noqa: N815
    maxPage = IntegerField(read_only=True, source="max_page")  # noqa: N815
    seriesName = CharField(read_only=True, source="series_name")  # noqa: N815
    volumeName = CharField(read_only=True, source="volume_name")  # noqa: N815


class ComicReaderInfoSerializer(Serializer):
    """Information when opening a new book."""

    comic = ComicReaderComicSerializer(read_only=True)
    routes = ComicReaderRoutesSerializer(read_only=True)
    browserRoute = JSONField(read_only=True, source="browser_route")  # noqa: N815
