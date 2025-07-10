"""Codex Reader Serializers."""

from rest_framework.fields import (
    BooleanField,
    CharField,
    DecimalField,
    DictField,
    IntegerField,
    ListField,
)
from rest_framework.serializers import Serializer
from typing_extensions import override

from codex.serializers.fields import (
    FitToField,
    ReadingDirectionField,
    TimestampField,
)
from codex.serializers.fields.reader import ArcGroupField
from codex.serializers.mixins import JSONFieldSerializer
from codex.serializers.route import RouteSerializer


class ReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fit_to = FitToField(allow_blank=True, required=False)
    two_pages = BooleanField(allow_null=True, required=False)
    reading_direction = ReadingDirectionField(allow_null=True, required=False)
    read_rtl_in_reverse = BooleanField(allow_null=True, required=False)
    finish_on_last_page = BooleanField(allow_null=True, required=False)
    mtime = TimestampField(read_only=True)
    page_transition = BooleanField(allow_null=True, required=False)


class ReaderComicSerializer(Serializer):
    """Prev, Next and Current Comic info."""

    pk = IntegerField(read_only=True)
    settings = ReaderSettingsSerializer(read_only=True)
    max_page = IntegerField(read_only=True)
    reading_direction = ReadingDirectionField(read_only=True)
    mtime = TimestampField(read_only=True)
    has_metadata = BooleanField(read_only=True)


class ReaderArcInfoSerializer(Serializer):
    """Information about the current Arc."""

    name = CharField(read_only=True)
    mtime = TimestampField(read_only=True)


class ReaderSelectedArcSerializer(Serializer):
    """And arc key serializer."""

    group = ArcGroupField(required=False)
    ids = ListField(child=IntegerField(), required=False)
    index = IntegerField(read_only=True, required=False)
    count = IntegerField(read_only=True, required=False)


class ReaderViewInputSerializer(JSONFieldSerializer):
    """Input for the reader serailizer."""

    JSON_FIELDS = frozenset({"arc"})

    arc = ReaderSelectedArcSerializer(required=False)


class ReaderCurrentComicSerializer(ReaderComicSerializer):
    """Current comic only Serializer."""

    # For title
    series_name = CharField(read_only=True, required=False)
    volume_name = CharField(read_only=True, required=False)
    volume_number_to = CharField(read_only=True, required=False)
    issue_number = DecimalField(
        max_digits=None,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
        required=False,
    )
    issue_suffix = CharField(read_only=True, required=False)
    issue_count = IntegerField(read_only=True, required=False)
    file_type = CharField(read_only=True, required=False)
    filename = CharField(read_only=True, required=False)
    name = CharField(read_only=True, required=False)


class ReaderBooksSerializer(Serializer):
    """All comics relevant to the reader."""

    current = ReaderCurrentComicSerializer(read_only=True)
    prev = ReaderComicSerializer(read_only=True, required=False)
    next = ReaderComicSerializer(read_only=True, required=False)


class ArcsIdsField(DictField):
    """Arcs Ids level."""

    @override
    def to_representation(self, value):
        """Serialize the ids to a string."""
        string_keyed_map = {}
        for ids, arc_info in value.items():
            string_key = ",".join(str(pk) for pk in ids)
            string_keyed_map[string_key] = arc_info

        return super().to_representation(string_keyed_map)

    child = ReaderArcInfoSerializer(read_only=True)


class ArcsField(DictField):
    """Arcs Field."""

    child = ArcsIdsField(read_only=True)


class ReaderComicsSerializer(Serializer):
    """Books and arcs."""

    arcs = ArcsField(read_only=True)
    arc = ReaderSelectedArcSerializer(read_only=True)
    books = ReaderBooksSerializer(read_only=True)
    close_route = RouteSerializer(read_only=True)
    mtime = TimestampField(read_only=True)
