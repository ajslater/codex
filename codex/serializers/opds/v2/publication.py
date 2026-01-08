"""OPDS 2 Publication Serializers."""

from rest_framework.fields import CharField, DateField, IntegerField, ListField
from rest_framework.serializers import Serializer

from codex.serializers.opds.v2.facet import OPDS2FacetSerializer
from codex.serializers.opds.v2.links import OPDS2LinkListField
from codex.serializers.opds.v2.metadata import OPDS2MetadataSerializer


class OPDS2FeedMetadataSerializer(OPDS2MetadataSerializer):
    """Feed Metadata."""

    items_per_page = IntegerField(read_only=True, required=False)
    current_page = IntegerField(read_only=True, required=False)
    number_of_items = IntegerField(read_only=True, required=False)


class OPDS2CreditObjectSerializer(Serializer):
    """
    Credit Object.

    https://readium.org/webpub-manifest/schema/credit-object.schema.json
    """

    name = CharField(read_only=True)
    # identifier= CharField(read_only=True, required=False)  unused
    # sort_as = CharField(read_only=True, required=False)  unused
    role = CharField(read_only=True, source="role_name")
    # role = CharListField(read_only=True)  unused
    # position = IntegerField(read_only=True, required=False)  unused
    # links = LinkListField(read_only=True)  unused
    #
    #


class OPDS2BelongsToSeriesSerializer(Serializer):
    """BelongsTo Series Field."""

    name = CharField(read_only=True)
    position = IntegerField(read_only=True, required=False)
    links = OPDS2LinkListField(read_only=True)


class OPDS2BelongsToMetadata(Serializer):
    """BelongsTo metadata field."""

    series = ListField(
        child=OPDS2BelongsToSeriesSerializer(read_only=True),
        read_only=True,
        required=False,
    )


class OPDS2PublicationMetadataSerializer(OPDS2MetadataSerializer):
    """
    Metadata for publications.

    https://readium.org/webpub-manifest/schema/metadata.schema.json
    """

    vars()["@type"] = CharField(read_only=True, default="https://schema.org/ComicIssue")
    publisher = CharField(read_only=True, required=False)
    imprint = CharField(read_only=True, required=False)
    identifier = CharField(read_only=True, required=False)
    language = CharField(read_only=True, required=False)
    published = DateField(read_only=True, required=False)
    # reading_progression = ChoiceField() unused

    #####################
    # Extended metadata #
    #####################
    subject = ListField(child=CharField(read_only=True), read_only=True, required=False)
    author = OPDS2CreditObjectSerializer(many=True, required=False)
    # translator = OPDS2CreditObjectSerializer(many=True, required=False) unused
    editor = OPDS2CreditObjectSerializer(many=True, required=False)
    artist = OPDS2CreditObjectSerializer(many=True, required=False)
    # illustrator = OPDS2CreditObjectSerializer(many=True, required=False) unused
    letterer = OPDS2CreditObjectSerializer(many=True, required=False)
    peniciller = OPDS2CreditObjectSerializer(many=True, required=False)
    colorist = OPDS2CreditObjectSerializer(many=True, required=False)
    inker = OPDS2CreditObjectSerializer(many=True, required=False)
    credit = OPDS2CreditObjectSerializer(many=True, required=False)

    # Manifest metadata
    belongs_to = OPDS2BelongsToMetadata(required=False)


class OPDS2PublicationSerializer(OPDS2FacetSerializer):
    """
    Publication.

    https://drafts.opds.io/schema/publication.schema.json
    """

    conforms_to = CharField(read_only=True)
    metadata = OPDS2PublicationMetadataSerializer(read_only=True)  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    links = OPDS2LinkListField(read_only=True)
    images = OPDS2LinkListField(read_only=True, required=False)


class OPDS2PublicationDivinaManifestSerializer(OPDS2PublicationSerializer):
    """
    Divina Visual Narratives Profile.

    https://readium.org/webpub-manifest/profiles/divina
    """

    vars()["@context"] = CharField(
        read_only=True, default="https://readium.org/webpub-manifest/context.jsonld"
    )
    reading_order = OPDS2LinkListField(read_only=True, required=False)
    resources = OPDS2LinkListField(read_only=True, required=False)
    toc = OPDS2LinkListField(read_only=True, required=False)
    landmarks = OPDS2LinkListField(read_only=True, required=False)
    page_list = OPDS2LinkListField(read_only=True, required=False)
