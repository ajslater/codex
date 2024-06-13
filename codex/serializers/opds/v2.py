"""OPDS 2 Serializers."""

from rest_framework.fields import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    ListField,
    SerializerMethodField,
)
from rest_framework.serializers import Serializer


class OPDS2LinkPropertiesSerializer(Serializer):
    """Link Properties.

    https://drafts.opds.io/schema/properties.schema.json
    """

    number_of_items = IntegerField(read_only=True, required=False)
    # price = OPDS2PriceSerializer(read_only=True, required=False)
    # indirect_aquisition = OPDS2AcquisitionObjectSerializer(
    #    read_only=True, many=True, required=False
    # )
    # holds = OPDS2HoldsSerializer(read_only=True, required=False)
    # copies = OPDS2CopiesSerializer(read_only=True, required=False)
    # availability = OPDS2AvailabilitySerializer(read_only=True, required=False)


class OPDS2LinkSerializer(Serializer):
    """Link.

    https://readium.org/webpub-manifest/schema/link.schema.json
    """

    href = CharField(
        read_only=True,
    )
    rel = SerializerMethodField(
        read_only=True,
    )
    templated = BooleanField(read_only=True, required=False)
    title = CharField(read_only=True, required=False)
    type = CharField(read_only=True, required=False)

    # Uncommon
    height = IntegerField(read_only=True, required=False)
    width = IntegerField(read_only=True, required=False)
    # bitrate = IntegerField(read_only=True, required=False)
    # duration = IntegerField(read_only=True, required=False)
    # language = CharField(many=True, read_only=True, required=False)
    alternate = ListField(child=CharField(), read_only=True, required=False)
    children = ListField(child=CharField(), read_only=True, required=False)
    properties = OPDS2LinkPropertiesSerializer(read_only=True, required=False)

    def get_rel(self, obj) -> str | None:
        """Allow for CharField or CharListField types."""
        rel = obj.get("rel")
        if not isinstance(rel, list | str):
            reason = "OPDS2LinkSerializer.rel is not a list or a string."
            raise TypeError(reason)
        return obj.get("rel")


class OPDS2LinkListField(ListField):
    """Link List."""

    child = OPDS2LinkSerializer()


class OPDS2MetadataSerializer(Serializer):
    """Metadata.

    https://drafts.opds.io/schema/feed-metadata.schema.json
    """

    identifier = CharField(read_only=True, required=False)
    title = CharField(
        read_only=True,
    )
    subtitle = CharField(read_only=True, required=False)
    modified = DateTimeField(read_only=True, required=False)
    description = CharField(read_only=True, required=False)


class OPDS2FeedMetadataSerializer(OPDS2MetadataSerializer):
    """Feed Metadata."""

    items_per_page = IntegerField(read_only=True, required=False)
    current_page = IntegerField(read_only=True, required=False)
    number_of_items = IntegerField(read_only=True, required=False)


class OPDS2ContributorObjectSerializer(Serializer):
    """Contributor Object.

    https://readium.org/webpub-manifest/schema/contributor-object.schema.json
    """

    name = CharField(read_only=True)
    # identifier= CharField(read_only=True, required=False)
    # sort_as = CharField(read_only=True, required=False)
    role = CharField(read_only=True, source="role_name")
    # role = CharListField(read_only=True)
    # position = IntegerField(read_only=True, required=False)
    # links = LinkListField(read_only=True)


class OPDS2PublicationMetadataSerializer(OPDS2MetadataSerializer):
    """Metadata for publications.

    https://readium.org/webpub-manifest/schema/metadata.schema.json
    """

    # possibly change to @ on output if this is really needed
    # @type = CharField(read_only=True, required=False)
    publisher = CharField(read_only=True, required=False)
    imprint = CharField(read_only=True, required=False)
    language = CharField(read_only=True, required=False)
    published = DateField(read_only=True, required=False)
    number_of_pages = IntegerField(read_only=True, required=False)
    # reading_progression = ChoiceField()

    #####################
    # Extended metadata #
    #####################
    subject = ListField(child=CharField(), read_only=True, required=False)
    author = OPDS2ContributorObjectSerializer(many=True, required=False)
    # translator = OPDS2ContributorObjectSerializer(many=True, required=False)
    editor = OPDS2ContributorObjectSerializer(many=True, required=False)
    artist = OPDS2ContributorObjectSerializer(many=True, required=False)
    # illustrator = OPDS2ContributorObjectSerializer(many=True, required=False)
    letterer = OPDS2ContributorObjectSerializer(many=True, required=False)
    peniciller = OPDS2ContributorObjectSerializer(many=True, required=False)
    colorist = OPDS2ContributorObjectSerializer(many=True, required=False)
    inker = OPDS2ContributorObjectSerializer(many=True, required=False)
    contributor = OPDS2ContributorObjectSerializer(many=True, required=False)


class OPDS2FacetSerializer(Serializer):
    """Facets."""

    metadata = OPDS2MetadataSerializer(read_only=True)
    links = OPDS2LinkListField(read_only=True)


class OPDS2PublicationSerializer(OPDS2FacetSerializer):
    """Publication.

    https://drafts.opds.io/schema/publication.schema.json
    """

    metadata = OPDS2PublicationMetadataSerializer(read_only=True)
    links = OPDS2LinkListField(read_only=True)
    images = OPDS2LinkListField(read_only=True, required=False)


class OPDS2GroupSerializer(Serializer):
    """Group."""

    metadata = OPDS2MetadataSerializer(read_only=True)
    links = OPDS2LinkListField(read_only=True, required=False)
    publications = ListField(
        child=OPDS2PublicationSerializer(), read_only=True, required=False
    )
    navigation = OPDS2LinkListField(read_only=True, required=False)


class OPDS2FeedSerializer(OPDS2GroupSerializer):
    """Feed.

    https://drafts.opds.io/schema/feed.schema.json
    https://readium.org/webpub-manifest/schema/subcollection.schema.json
    """

    facets = ListField(child=OPDS2FacetSerializer(), read_only=True, required=False)
    groups = ListField(child=OPDS2GroupSerializer(), read_only=True, required=False)
