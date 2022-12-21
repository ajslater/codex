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


class ReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fit_to = ChoiceField(
        choices=FIT_TO_CHOICES,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    two_pages = BooleanField(allow_null=True, required=False)


class ReaderComicSerializer(Serializer):
    """Components for constructing the title."""

    pk = IntegerField(read_only=True)
    file_format = CharField(read_only=True)
    issue = DecimalField(
        max_digits=None, decimal_places=3, read_only=True, coerce_to_string=False
    )
    issue_suffix = CharField(read_only=True)
    issue_count = IntegerField(read_only=True)
    max_page = IntegerField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    series_index = IntegerField(read_only=True)
    settings = ReaderSettingsSerializer(read_only=True)


class ReaderInfoSerializer(Serializer):
    """Information about the series this comic belongs to."""

    books = ReaderComicSerializer(many=True, read_only=True)
    series_count = IntegerField(read_only=True)
