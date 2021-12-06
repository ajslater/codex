"""Serializers for codex models."""
import pycountry

from rest_framework.serializers import (
    IntegerField,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)

from codex.models import (
    Character,
    Comic,
    Credit,
    CreditPerson,
    CreditRole,
    Genre,
    Imprint,
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
    """
    PyCountry tag serializer to include long names.

    Takes a single string value and serializes the value to
    a pk attribute and a pycountry long name lookup of that value to
    the name.
    """

    LOOKUP_MODULE = pycountry.countries

    pk = SerializerMethodField()
    name = SerializerMethodField()

    class Meta:
        """Abstract class."""

        abstract = True

    def get_pk(self, obj):
        """Return submitted value as the key."""
        return obj

    def get_name(self, obj):
        """Lookup the name with pycountry, just copy the key on fail."""
        if obj is None:
            # This never seems to get called so I do it on the front end.
            return "None"
        if len(obj) == 2:
            # fix for https://github.com/flyingcircusio/pycountry/issues/41
            lookup_obj = self.LOOKUP_MODULE.get(alpha_2=obj)
        else:
            lookup_obj = self.LOOKUP_MODULE.lookup(obj)
        if lookup_obj:
            value = lookup_obj.name
        else:
            # If lookup fails, return the key as the name
            value = obj
        return value


class LanguageSerializer(PyCountrySerializer):
    """Pycountry serializer for language field."""

    LOOKUP_MODULE = pycountry.languages


class CountrySerializer(PyCountrySerializer):
    """Pycountry serializer for country field."""

    pass


class NamedModelMeta:
    """Meta class for named models."""

    fields = ("pk", "name")


##########
# Groups #
##########


class GroupModelMeta:
    """Meta class for group models."""

    fields = NamedModelMeta.fields


class NamedModelSerializer(ModelSerializer):
    """A common class for NamedModels."""

    class Meta:
        """Abstract class."""

        abstract = True


class GroupModelSerializer(NamedModelSerializer):
    """A common class for BrowserGroupModels."""

    class Meta:
        """Abstract class."""

        abstract = True


class PublisherSerializer(GroupModelSerializer):
    """Publisher Model."""

    class Meta(GroupModelMeta):
        """Configure model."""

        model = Publisher


class ImprintSerializer(GroupModelSerializer):
    """Imprint Model."""

    class Meta(GroupModelMeta):
        """Configure model."""

        model = Imprint


class SeriesSerializer(GroupModelSerializer):
    """Series Model."""

    class Meta(GroupModelMeta):
        """Configure model."""

        model = Series


class VolumeSerializer(GroupModelSerializer):
    """Volume Model."""

    class Meta(GroupModelMeta):
        """Configure model."""

        model = Volume


##############
# ManyToMany #
##############


class CreditPersonSerializer(NamedModelSerializer):
    """CreditPerson model."""

    class Meta(NamedModelMeta):
        """Configure model."""

        model = CreditPerson


class CreditRoleSerializer(NamedModelSerializer):
    """CreditRole model."""

    class Meta(NamedModelMeta):
        """Configure model."""

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

    def __init__(self, *args, **kwargs):
        """Dynamically whitelist fields."""
        fields = kwargs.pop("fields", None)
        # Use the fields argument to remove fields not in the list.
        if fields:
            allowed_fields = set(fields)
            existing_fields = set(self.fields.keys())
            excluded_fields = existing_fields - allowed_fields
            for field in excluded_fields:
                self.fields.pop(field)
        super().__init__(*args, **kwargs)

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
        """Configure the model."""

        model = Comic
        fields = "__all__"  # Overridden dynamically by constructor param
        depth = 1
