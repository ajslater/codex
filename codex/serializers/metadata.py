"""Codex Serializers for the metadata box."""
import pycountry

from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import ListField
from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import Serializer
from rest_framework.serializers import SerializerMethodField

from codex.models import Character
from codex.models import Comic
from codex.models import Credit
from codex.models import CreditPerson
from codex.models import CreditRole
from codex.models import Genre
from codex.models import Imprint
from codex.models import Location
from codex.models import Publisher
from codex.models import Series
from codex.models import SeriesGroup
from codex.models import StoryArc
from codex.models import Tag
from codex.models import Team
from codex.models import UserBookmark
from codex.models import Volume


class PyCountrySerializer(Serializer):
    """
    Takes a single string value and serializes the value to
    a pk attribute and a pycountry long name lookup of that value to
    the name.
    """

    pk = SerializerMethodField()
    name = SerializerMethodField()

    class Meta:
        abstract = True

    def get_pk(self, obj):
        return obj

    def get_name(self, obj):
        value = obj
        if not value:
            return
        if len(value) == 2:
            # fix for https://github.com/flyingcircusio/pycountry/issues/41
            lookup_obj = self.LOOKUP_MODULE.get(alpha_2=value)
        else:
            lookup_obj = self.LOOKUP_MODULE.lookup(value)
        if lookup_obj:
            return lookup_obj.name
        # If lookup fails, return the key as the name
        return value


class LanguageSerializer(PyCountrySerializer):
    """Pycountry serializer for langauge field."""

    LOOKUP_MODULE = pycountry.languages


class CountrySerializer(PyCountrySerializer):
    """Pycountry serializer for country field."""

    LOOKUP_MODULE = pycountry.countries


class NamedModelMeta:
    """Meta class for named models."""

    fields = ("pk", "name")


##########
# Groups #
##########


class GroupModelMeta:
    """Meta class for group models."""

    fields = ("pk", "name", "is_default")


class NamedModelSerializer(ModelSerializer):
    class Meta:
        abstract = True


class PublisherSerializer(NamedModelSerializer):
    class Meta(GroupModelMeta):

        model = Publisher


class ImprintSerializer(NamedModelSerializer):
    class Meta(GroupModelMeta):

        model = Imprint


class SeriesSerializer(NamedModelSerializer):
    class Meta(GroupModelMeta):

        model = Series


class VolumeSerializer(NamedModelSerializer):
    class Meta(GroupModelMeta):

        model = Volume


##############
# ManyToMany #
##############


class CreditPersonSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = CreditPerson


class CreditRoleSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = CreditRole


class CreditSerializer(ModelSerializer):
    """Credit model serializer."""

    role = CreditRoleSerializer()
    person = CreditPersonSerializer()

    class Meta:
        """Model spec."""

        model = Credit
        fields = ("pk", "person", "role")
        depth = 1


class CharacterSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = Character


class GenreSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = Genre


class LocationSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = Location


class SeriesGroupSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = SeriesGroup


class StoryArcSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = StoryArc


class TagSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = Tag


class TeamSerializer(NamedModelSerializer):
    class Meta(NamedModelMeta):

        model = Team


class MetadataContainerSerializer(Serializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    # Aggregate Annotations
    size = IntegerField(read_only=True)
    x_cover_path = CharField(read_only=True)
    x_page_count = IntegerField(read_only=True)

    # UserBookmark annotations
    bookmark = IntegerField(read_only=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(max_digits=5, decimal_places=2, read_only=True)


class ComicSerializer(ModelSerializer):
    """Serialize a comic object for the metadata dialog."""

    def __init__(self, *args, **kwargs):
        """Special init for removing fields not in the fields argument."""
        # Instantiate the superclass normally
        fields = kwargs.get("fields")
        kwargs.pop("fields")
        super().__init__(*args, **kwargs)

        # Use the fields argument to remove fields not in the list.
        # TODO can i do this before the constructor?
        if not fields:
            return
        allowed_fields = set(fields)
        existing_fields = set(self.fields.keys())
        excluded_fields = existing_fields - allowed_fields
        for field in excluded_fields:
            self.fields.pop(field)

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
    seriesGroups = SeriesGroupSerializer(many=True, allow_null=True)  # noqa: N815
    storyArcs = StoryArcSerializer(many=True, allow_null=True)  # noqa: N815
    tags = TagSerializer(many=True, allow_null=True)
    teams = TeamSerializer(many=True, allow_null=True)
    credits = CreditSerializer(many=True, allow_null=True)

    class Meta:
        model = Comic
        fields = "__all__"  # Overriden dynamically by constructor param
        depth = 1


class MetadataSerializer(Serializer):
    """Data for the metadata dialog."""

    def __init__(self, *args, **kwargs):
        """Dynamically create comic field with 'fields' argument."""
        comic_fields = kwargs.get("comic_fields")
        self.fields["comic"] = ComicSerializer(fields=comic_fields)
        kwargs.pop("comic_fields")
        super().__init__(*args, **kwargs)

    # All the comic pks for a filtered aggregate group
    pks = ListField(child=IntegerField())

    # Aggregated stats for the group of comics selected.
    container = MetadataContainerSerializer()


class UserBookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the UserBookmark."""

    class Meta:
        """Model spec."""

        model = UserBookmark
        fields = ("finished",)
