"""Codex Reader Serializers."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DateTimeField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.models import Bookmark


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


class ReaderArcSerializer(Serializer):
    """A group of comics or a story arc."""

    group = CharField(read_only=True)
    pk = IntegerField(read_only=True)
    name = CharField(read_only=True)


class ReaderComicSerializer(Serializer):
    """Prev, Next and Current Comic info."""

    pk = IntegerField(read_only=True)
    settings = ReaderSettingsSerializer(read_only=True)
    max_page = IntegerField(read_only=True)
    reading_direction = CharField(read_only=True)
    mtime = DateTimeField(format="%s", read_only=True)


class ReaderCurrentArcSerializer(Serializer):
    """Information about the current Arc."""

    group = CharField(read_only=True)
    pk = IntegerField(read_only=True)
    index = IntegerField(read_only=True)
    count = IntegerField(read_only=True, required=False)


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


class ReaderBooksSerializer(Serializer):
    """All comics relevant to the reader."""

    current = ReaderCurrentComicSerializer(read_only=True)
    prev_book = ReaderComicSerializer(read_only=True, required=False)
    next_book = ReaderComicSerializer(read_only=True, required=False)


class ReaderComicsSerializer(Serializer):
    """Books and arcs."""

    books = ReaderBooksSerializer(read_only=True)
    arcs = ReaderArcSerializer(many=True, read_only=True)
    arc = ReaderCurrentArcSerializer(read_only=True)
