"""Codex Reader Serializers."""
from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import ChoiceField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import Serializer

from codex_api.choices.static import CHOICES


class ComicPageRouteSerializer(Serializer):
    """A comic page route."""

    pk = IntegerField(read_only=True)
    pageNumber = IntegerField(read_only=True)  # noqa: N815


class ComicReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fitTo = ChoiceField(  # noqa: N815
        choices=tuple(CHOICES["fitToChoices"].keys()), required=False,
    )
    twoPages = BooleanField(required=False)  # noqa: N815


class ComicReaderInfoSerializer(Serializer):
    """Information when opening a new book."""

    title = CharField(read_only=True)  # noqa: N815
    maxPage = IntegerField(read_only=True)  # noqa: N815
    settings = ComicReaderSettingsSerializer(read_only=True)
    prevComicPage = ComicPageRouteSerializer(  # noqa: N815
        allow_null=True, read_only=True
    )
    nextComicPage = ComicPageRouteSerializer(  # noqa: N815
        allow_null=True, read_only=True
    )
