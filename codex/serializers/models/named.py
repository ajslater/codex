"""Named model Serializers."""

from rest_framework.fields import CharField
from rest_framework.serializers import URLField

from codex.models import (
    AgeRating,
    AgeRatingMetron,
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


class IdentifierSerializer(BaseModelSerializer):
    """
    Identifier model.

    ``Identifier.name`` is a model-side ``@property`` that reads
    ``self.source`` (FK to ``IdentifierSource``) — accessing ``name``
    triggers a DB hit unless ``source`` is preloaded. Today the only
    consumer is the metadata pane via ``MetadataSerializer``'s
    ``identifiers`` field, which is populated from
    ``M2M_QUERY_OPTIMIZERS[Identifier]`` with ``select=("source",)``.
    Other paths reach Identifier transitively (Credit.role.identifier,
    StoryArcNumber.story_arc.identifier) but only read ``.url`` —
    ``url`` is a column, not a property, so no FK fan-out.

    Adding any field to this serializer that triggers further FK
    access on ``Identifier`` (or the optimizer dropping ``source``)
    breaks the invariant.
    """

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


class AgeRatingMetronSerializer(NamedModelSerializer):
    """Age Rating Metron model."""

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = AgeRatingMetron
        fields = ("pk", "name", "index")


class AgeRatingSerializer(NamedModelSerializer):
    """Age Rating model."""

    metron = AgeRatingMetronSerializer(allow_null=True, read_only=True)

    class Meta(NamedModelSerializer.Meta):
        """Configure model."""

        model = AgeRating
        fields = ("pk", "name", "metron")


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
