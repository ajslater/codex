"""Codex Serializers for the metadata box."""
import pycountry

from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import Serializer
from rest_framework.serializers import SerializerMethodField

from codex.models import Comic
from codex.models import Credit
from codex.models import UserBookmark


class NamedModelSerializer(Serializer):
    """One serializer for all NamedModels."""

    pk = IntegerField()
    name = CharField(max_length=32)


# Cannot use ModelSerializer with Abstract Models... for now.
#    class Meta:
#        """Model spec."""
#
#        model = NamedModel
#        fields = ("pk", "name")
#        read_only_fields = fields


class CreditSerializer(ModelSerializer):
    """Credit model serializer."""

    person = NamedModelSerializer(read_only=True)
    role = NamedModelSerializer(read_only=True)

    class Meta:
        """Model spec."""

        model = Credit
        fields = ("person", "role")
        read_only_fields = fields


class ComicSerializer(ModelSerializer):
    """Serialize the comic model for browser metadata box."""

    # Publish annotations
    publisher_name = CharField()
    imprint_name = CharField()
    series_name = CharField()
    volume_name = CharField()
    volume_count = IntegerField()
    issue_count = IntegerField()

    # UserBookmark annotations
    bookmark = IntegerField()
    finished = BooleanField()
    fit_to = CharField()
    two_pages = BooleanField()
    progress = DecimalField(max_digits=5, decimal_places=2)

    # Pycountry
    country = SerializerMethodField()
    language = SerializerMethodField()

    # Many to many NamedModel
    genres = NamedModelSerializer(many=True)
    tags = NamedModelSerializer(many=True)
    teams = NamedModelSerializer(many=True)
    characters = NamedModelSerializer(many=True)
    locations = NamedModelSerializer(many=True)
    series_groups = NamedModelSerializer(many=True)
    story_arcs = NamedModelSerializer(many=True)
    credits = CreditSerializer(many=True)

    def get_country(self, obj):
        """Long name from alpha2 country."""
        if obj.country:
            country = pycountry.countries.lookup(obj.country)
            if country:
                return country.name

    def get_language(self, obj):
        """Long name from alpha2 language."""
        if obj.language:
            language = pycountry.languages.lookup(obj.language)
            if language:
                return language.name

    class Meta:
        """Fields to serialize."""

        model = Comic
        fields = (
            "pk",
            "publisher_name",
            "imprint_name",
            "series_name",
            "volume_name",
            "volume_count",
            "issue",
            "issue_count",
            "title",
            "cover_path",
            "year",
            "month",
            "day",
            "format",
            "read_ltr",
            "size",
            "web",
            "user_rating",
            "critical_rating",
            "maturity_rating",
            "summary",
            "description",
            "notes",
            # Pycountry alpha2
            "country",
            "language",
            # Many to many NamedModels
            "genres",
            "tags",
            "teams",
            "characters",
            "locations",
            "series_groups",
            "story_arcs",
            "scan_info",
            "credits",
            # UserBookmark annotations
            "finished",
            "fit_to",
            "two_pages",
            "bookmark",
            "page_count",
            "progress",
        )
        read_only_fields = fields


class UserBookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the UserBookmark."""

    class Meta:
        """Model spec."""

        model = UserBookmark
        fields = ("finished",)
