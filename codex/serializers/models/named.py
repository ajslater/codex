"""Named model Serializers."""

from rest_framework.fields import CharField
from rest_framework.serializers import URLField

from codex.models import (
    AgeRating,
    Character,
    Credit,
    CreditPerson,
    CreditRole,
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
from codex.models.identifier import Identifier, IdentifierSource
from codex.models.named import Universe
from codex.serializers.models.base import BaseModelSerializer


class NamedModelSerializer(BaseModelSerializer):
    """A common class for NamedModels."""

    class Meta(BaseModelSerializer.Meta):
        """Abstract."""

        fields: tuple[str, ...] = ("pk", "name")
        abstract = True


class URLNamedModelSerializer(NamedModelSerializer):
    """A common class for NamedModels with URLs."""

    url = URLField(read_only=True, source="identifier.url")

    class Meta(NamedModelSerializer.Meta):
        """Abstract."""

        fields: tuple[str, ...] = ("pk", "name", "url")
        abstract = True


class CreditPersonSerializer(URLNamedModelSerializer):
    """CreditPerson model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = CreditPerson


class CreditRoleSerializer(URLNamedModelSerializer):
    """CreditRole model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = CreditRole


class CreditSerializer(BaseModelSerializer):
    """Credit model serializer."""

    role = CreditRoleSerializer()
    person = CreditPersonSerializer()

    class Meta(BaseModelSerializer.Meta):
        """Model spec."""

        model = Credit
        fields = ("pk", "person", "role")
        depth = 1


class CharacterSerializer(URLNamedModelSerializer):
    """Character model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Character


class GenreSerializer(URLNamedModelSerializer):
    """Genre model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Genre


class IdentifierSourceSerializer(NamedModelSerializer):
    """IdentifierSource model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = IdentifierSource


class IdentifierSeralizer(BaseModelSerializer):
    """Identifier model."""

    name = CharField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        """Configure model."""

        model = Identifier
        fields = ("pk", "name", "key", "url")
        depth = 1


class LocationSerializer(URLNamedModelSerializer):
    """Location model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Location


class SeriesGroupSerializer(NamedModelSerializer):
    """SeriesGroup model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = SeriesGroup


class StorySerializer(URLNamedModelSerializer):
    """StoryArc model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Story


class StoryArcSerializer(URLNamedModelSerializer):
    """StoryArc model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = StoryArc


class StoryArcNumberSerializer(BaseModelSerializer):
    """StoryArc model."""

    name = CharField(read_only=True)
    url = URLField(read_only=True, source="story_arc.identifier.url")

    class Meta(BaseModelSerializer.Meta):
        """Configure model."""

        model = StoryArcNumber
        fields = ("pk", "name", "number", "url")
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


class TagSerializer(URLNamedModelSerializer):
    """Tag model."""

    class Meta(URLNamedModelSerializer.Meta):
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


class TeamSerializer(URLNamedModelSerializer):
    """Team model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Team


class UniverseSerializer(URLNamedModelSerializer):
    """Team model."""

    class Meta(URLNamedModelSerializer.Meta):
        """Configure model."""

        model = Universe
        fields: tuple[str, ...] = ("pk", "name", "designation", "url")
