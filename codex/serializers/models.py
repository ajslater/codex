"""Serializers for codex models."""
import pycountry
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import (
    IntegerField,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)

from codex.models import (
    Bookmark,
    Character,
    Comic,
    Creator,
    CreatorPerson,
    CreatorRole,
    Genre,
    Imprint,
    LibrarianStatus,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
    Volume,
)


class PyCountrySerializer(Serializer):
    """PyCountry tag serializer to include long names.

    Takes a single string value and serializes the value to
    a pk attribute and a pycountry long name lookup of that value to
    the name.
    """

    LOOKUP_MODULE = pycountry.countries
    _ALPHA_2_LEN = 2

    pk = SerializerMethodField()
    name = SerializerMethodField()

    class Meta:
        """Abstract class."""

        abstract = True

    @extend_schema_field(OpenApiTypes.STR)
    def get_pk(self, pk):
        """Return submitted value as the key."""
        return pk

    @classmethod
    def lookup_name(cls, lookup_module, name):
        """Lookup the name with pycountry, just copy the key on fail."""
        if not name:
            return ""
        # fix for https://github.com/flyingcircusio/pycountry/issues/41
        lookup_obj = (
            lookup_module.get(alpha_2=name)
            if len(name) == cls._ALPHA_2_LEN
            else lookup_module.lookup(name)
        )
        # If lookup fails, return the key as the name
        return lookup_obj.name if lookup_obj else name

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, name):
        """Lookup the name with pycountry, just copy the key on fail."""
        return self.lookup_name(self.LOOKUP_MODULE, name)


class LanguageSerializer(PyCountrySerializer):
    """Pycountry serializer for language field."""

    LOOKUP_MODULE = pycountry.languages


class CountrySerializer(PyCountrySerializer):
    """Pycountry serializer for country field."""


class NamedModelMeta:
    """Meta class for named models."""

    fields = ("pk", "name")


##########
# Groups #
##########


class NamedModelSerializer(ModelSerializer):
    """A common class for NamedModels."""

    class Meta(NamedModelMeta):
        """Not Abstract."""

        abstract = True


class GroupModelSerializer(NamedModelSerializer):
    """A common class for BrowserGroupModels."""

    class Meta(NamedModelMeta):
        """Abstract class."""

        abstract = True


class PublisherSerializer(GroupModelSerializer):
    """Publisher Model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Publisher


class ImprintSerializer(GroupModelSerializer):
    """Imprint Model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Imprint


class SeriesSerializer(GroupModelSerializer):
    """Series Model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Series


class VolumeSerializer(GroupModelSerializer):
    """Volume Model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Volume


##############
# ManyToMany #
##############


class CreatorPersonSerializer(NamedModelSerializer):
    """CreatorPerson model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = CreatorPerson


class CreatorRoleSerializer(NamedModelSerializer):
    """CreatorRole model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = CreatorRole


class CreatorSerializer(ModelSerializer):
    """Creator model serializer."""

    role = CreatorRoleSerializer()
    person = CreatorPersonSerializer()

    class Meta:
        """Model spec."""

        model = Creator
        fields = ("pk", "person", "role")
        depth = 1


class CharacterSerializer(NamedModelSerializer):
    """Character model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Character


class GenreSerializer(NamedModelSerializer):
    """Genre model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Genre


class LocationSerializer(NamedModelSerializer):
    """Location model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Location


class SeriesGroupSerializer(NamedModelSerializer):
    """SeriesGroup model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = SeriesGroup


class StoryArcSerializer(NamedModelSerializer):
    """StoryArc model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = StoryArc


class TagSerializer(NamedModelSerializer):
    """Tag model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Tag


class TeamSerializer(NamedModelSerializer):
    """Team model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = Team


class ComicSerializer(ModelSerializer):
    """Serialize a comic object for the metadata dialog."""

    # Easier than specifying fields in Meta
    pk = IntegerField(source="id")

    # Annotations
    issue_count = IntegerField(allow_null=True)
    volume_count = IntegerField(allow_null=True)

    # Special Serialization with pycountry
    country = CountrySerializer(allow_null=True)
    language = LanguageSerializer(allow_null=True)

    # FKs
    publisher = PublisherSerializer(allow_null=True)
    imprint = ImprintSerializer(allow_null=True)
    series = SeriesSerializer(allow_null=True)
    volume = VolumeSerializer(allow_null=True)

    # ManyToMany
    characters = CharacterSerializer(many=True, allow_null=True)
    genres = GenreSerializer(many=True, allow_null=True)
    locations = LocationSerializer(many=True, allow_null=True)
    series_groups = SeriesGroupSerializer(many=True, allow_null=True)
    story_arcs = StoryArcSerializer(
        many=True,
        allow_null=True,
    )
    tags = TagSerializer(many=True, allow_null=True)
    teams = TeamSerializer(many=True, allow_null=True)
    creators = CreatorSerializer(many=True, allow_null=True)

    class Meta:
        """Configure the model."""

        model = Comic
        exclude = ("folders", "parent_folder", "stat")
        depth = 1


class LibrarianStatusSerializer(ModelSerializer):
    """Serializer Librarian task statuses."""

    class Meta:
        """Configure the model."""

        model = LibrarianStatus
        exclude = ("active", "created_at", "updated_at")


class BookmarkSerializer(ModelSerializer):
    """Serializer Bookmark."""

    class Meta:
        """Configure the model."""

        model = Bookmark
        fields = (
            "finished",
            "fit_to",
            "page",
            "two_pages",
            "read_in_reverse",
            "vertical",
        )


class BookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the Bookmark."""

    class Meta:
        """Model spec."""

        model = Bookmark
        fields = ("finished",)
