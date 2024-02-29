"""Serializers for codex models."""

from rest_framework.serializers import IntegerField

from codex.models import (
    Comic,
)
from codex.serializers.models.base import BaseModelSerializer
from codex.serializers.models.groups import (
    ImprintSerializer,
    PublisherSerializer,
    SeriesSerializer,
    VolumeSerializer,
)
from codex.serializers.models.named import (
    AgeRatingSerializer,
    CharacterSerializer,
    ContributorSerializer,
    GenreSerializer,
    IdentifierSeralizer,
    LocationSerializer,
    OriginalFormatSerializer,
    ScanInfoSerializer,
    SeriesGroupSerializer,
    StoryArcNumberSerializer,
    StorySerializer,
    TaggerSerializer,
    TagSerializer,
    TeamSerializer,
)
from codex.serializers.models.pycountry import CountrySerializer, LanguageSerializer


class ComicSerializer(BaseModelSerializer):
    """Serialize a comic object for the metadata dialog."""

    # Easier than specifying fields in Meta
    pk = IntegerField(source="id")

    # Annotations
    # issue_count = IntegerField(allow_null=True)
    # volume_count = IntegerField(allow_null=True)

    # Group FKs
    publisher = PublisherSerializer(allow_null=True)
    imprint = ImprintSerializer(allow_null=True)
    series = SeriesSerializer(allow_null=True)
    volume = VolumeSerializer(allow_null=True)

    # Special Serialization with pycountry
    country = CountrySerializer(allow_null=True)
    language = LanguageSerializer(allow_null=True)

    # Other FKS
    age_rating = AgeRatingSerializer(allow_null=True)
    original_format = OriginalFormatSerializer(allow_null=True)
    scan_info = ScanInfoSerializer(allow_null=True)
    tagger = TaggerSerializer(allow_null=True)

    # ManyToMany
    characters = CharacterSerializer(many=True, allow_null=True)
    genres = GenreSerializer(many=True, allow_null=True)
    identifiers = IdentifierSeralizer(many=True, allow_null=True)
    locations = LocationSerializer(many=True, allow_null=True)
    series_groups = SeriesGroupSerializer(many=True, allow_null=True)
    stories = StorySerializer(many=True, allow_null=True)
    story_arc_numbers = StoryArcNumberSerializer(
        many=True,
        allow_null=True,
    )
    tags = TagSerializer(many=True, allow_null=True)
    teams = TeamSerializer(many=True, allow_null=True)
    contributors = ContributorSerializer(many=True, allow_null=True)

    class Meta(BaseModelSerializer.Meta):
        """Configure the model."""

        model = Comic
        exclude = ("folders", "parent_folder", "stat")
        depth = 1
