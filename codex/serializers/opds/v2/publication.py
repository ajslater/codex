"""OPDS 2 Publication Serializers."""

from rest_framework.fields import CharField, DateField, IntegerField, ListField
from rest_framework.serializers import Serializer

from codex.serializers.opds.v2.facet import OPDS2FacetSerializer
from codex.serializers.opds.v2.links import OPDS2LinkListField
from codex.serializers.opds.v2.metadata import OPDS2MetadataSerializer


class OPDS2ContributorSerializer(Serializer):
    """
    Credit Object.

    https://readium.org/webpub-manifest/schema/contributor.schema.json
    """

    name = CharField(read_only=True)
    identifier = CharField(read_only=True, required=False)
    # X alt_identifier = CharField(read_only=True, required=False)
    # X sort_as = CharField(read_only=True, required=False)  unused
    role = CharField(read_only=True, source="role_name", required=False)
    # X role = CharListField(read_only=True)  unused
    links = OPDS2LinkListField(read_only=True)


class OPDS2BelongsToObjectSerializer(Serializer):
    """BelongsTo Series Field."""

    name = CharField(read_only=True)
    position = IntegerField(read_only=True, required=False)
    links = OPDS2LinkListField(read_only=True)


class OPDS2BelongsTo(Serializer):
    """BelongsTo metadata field."""

    collection = ListField(
        child=OPDS2BelongsToObjectSerializer(read_only=True),
        read_only=True,
        required=False,
    )
    series = ListField(
        child=OPDS2BelongsToObjectSerializer(read_only=True),
        read_only=True,
        required=False,
    )
    story_arc = ListField(
        child=OPDS2BelongsToObjectSerializer(read_only=True),
        read_only=True,
        required=False,
    )


class OPDS2PublicationMetadataSerializer(OPDS2MetadataSerializer):
    """
    Metadata for publications.

    https://readium.org/webpub-manifest/schema/metadata.schema.json
    """

    vars()["@type"] = CharField(read_only=True, default="https://schema.org/ComicIssue")
    conforms_to = CharField(
        read_only=True,
        default="https://readium.org/webpub-manifest/schema/metadata.schema.json",
    )

    # X sort_as = CharField(read_only=True, required=False)
    # X alt_identifier = CharField(read_only=True, required=False)
    # X accessibility = OPDS2Accessibility(read_only=True, required=False)
    published = DateField(read_only=True, required=False)
    # reading_progression = ChoiceField() unused

    #####################
    # Extended metadata #
    #####################
    language = CharField(read_only=True, required=False)
    author = OPDS2ContributorSerializer(many=True, required=False)
    translator = OPDS2ContributorSerializer(many=True, required=False)
    editor = OPDS2ContributorSerializer(many=True, required=False)
    artist = OPDS2ContributorSerializer(many=True, required=False)
    illustrator = OPDS2ContributorSerializer(many=True, required=False)
    letterer = OPDS2ContributorSerializer(many=True, required=False)
    peniciller = OPDS2ContributorSerializer(many=True, required=False)
    colorist = OPDS2ContributorSerializer(many=True, required=False)
    inker = OPDS2ContributorSerializer(many=True, required=False)
    narrator = OPDS2ContributorSerializer(many=True, required=False)
    contributor = OPDS2ContributorSerializer(many=True, required=False)
    publisher = CharField(read_only=True, required=False)
    imprint = CharField(read_only=True, required=False)
    subject = ListField(child=CharField(read_only=True), read_only=True, required=False)
    layout = CharField(read_only=True, required=False)
    reading_progression = CharField(read_only=True, required=False)  # choice field
    # X duration = InteField(read_only=True, required=False)
    belongs_to = OPDS2BelongsTo(required=False)
    # X contains = OPDS2Containse(required=False)
    # X tdm = OPDS2TDM(required=False)


class OPDS2PublicationSerializer(OPDS2FacetSerializer):
    """
    Publication.

    https://drafts.opds.io/schema/publication.schema.json
    """

    conforms_to = CharField(
        read_only=True, default="https://drafts.opds.io/schema/publication.schema.json"
    )
    metadata = OPDS2PublicationMetadataSerializer(read_only=True)  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    links = OPDS2LinkListField(read_only=True)
    images = OPDS2LinkListField(read_only=True, required=False)


class OPDS2PublicationDivinaMetadataSerializer(OPDS2PublicationMetadataSerializer):
    """
    Divina Visual Narratives Metadata.

    https://readium.org/webpub-manifest/profiles/divina
    """

    conforms_to = CharField(
        read_only=True, default="https://readium.org/webpub-manifest/profiles/divina "
    )


class OPDS2PublicationDivinaManifestSerializer(OPDS2PublicationSerializer):
    """
    Divina Visual Narratives Profile.

    https://readium.org/webpub-manifest/profiles/divina
    """

    vars()["@context"] = CharField(
        read_only=True, default="https://readium.org/webpub-manifest/context.jsonld"
    )
    conforms_to = CharField(
        read_only=True, default="https://readium.org/webpub-manifest/profiles/divina"
    )

    metadata = OPDS2PublicationDivinaMetadataSerializer(read_only=True)  # pyright: ignore[reportIncompatibleUnannotatedOverride]

    reading_order = OPDS2LinkListField(read_only=True, required=False)

    # X resources = OPDS2LinkListField(read_only=True, required=False)
    # X toc = OPDS2LinkListField(read_only=True, required=False)
    # X landmarks = OPDS2LinkListField(read_only=True, required=False)
    # X page_list = OPDS2LinkListField(read_only=True, required=False)
