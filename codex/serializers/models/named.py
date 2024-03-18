"""Named model Serializers."""

from rest_framework.serializers import CharField

from codex.models import (
    AgeRating,
    Character,
    Contributor,
    ContributorPerson,
    ContributorRole,
    Genre,
    Location,
    OriginalFormat,
    ScanInfo,
    SeriesGroup,
    Story,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
)
from codex.models.named import Identifier, IdentifierType
from codex.serializers.models.base import BaseModelSerializer


class NamedModelSerializer(BaseModelSerializer):
    """A common class for NamedModels."""

    class Meta(BaseModelSerializer.Meta):
        """Not Abstract."""

        fields = ("pk", "name")
        abstract = True


class ContributorPersonSerializer(NamedModelSerializer):
    """ContributorPerson model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = ContributorPerson


class ContributorRoleSerializer(NamedModelSerializer):
    """ContributorRole model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = ContributorRole


class ContributorSerializer(BaseModelSerializer):
    """Contributor model serializer."""

    role = ContributorRoleSerializer()
    person = ContributorPersonSerializer()

    class Meta(BaseModelSerializer.Meta):
        """Model spec."""

        model = Contributor
        fields = ("pk", "person", "role")
        depth = 1


class CharacterSerializer(NamedModelSerializer):
    """Character model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Character


class GenreSerializer(NamedModelSerializer):
    """Genre model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Genre


class IdentifierTypeSerializer(NamedModelSerializer):
    """IdentifierType model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = IdentifierType


class IdentifierSeralizer(BaseModelSerializer):
    """Identifier model."""

    name = CharField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        """Configure model."""

        model = Identifier
        fields = ("pk", "name", "nss", "url")
        depth = 1


class LocationSerializer(NamedModelSerializer):
    """Location model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Location


class SeriesGroupSerializer(NamedModelSerializer):
    """SeriesGroup model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = SeriesGroup


class StorySerializer(NamedModelSerializer):
    """StoryArc model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Story


class StoryArcSerializer(NamedModelSerializer):
    """StoryArc model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = StoryArc


class StoryArcNumberSerializer(BaseModelSerializer):
    """StoryArc model."""

    name = CharField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        """Configure model."""

        model = StoryArcNumber
        fields = ("pk", "name", "number")
        depth = 1


class TaggerSerializer(NamedModelSerializer):
    """Tag model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Tagger


class AgeRatingSerializer(NamedModelSerializer):
    """Age Rating model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = AgeRating


class TagSerializer(NamedModelSerializer):
    """Tag model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Tag


class OriginalFormatSerializer(NamedModelSerializer):
    """Original Format model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = OriginalFormat


class ScanInfoSerializer(NamedModelSerializer):
    """Scan Info model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = ScanInfo


class TeamSerializer(NamedModelSerializer):
    """Team model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = Team
