"""Browser Collection Model Serializers."""

from codex.models import (
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.serializers.models.named import NamedModelSerializer


class CollectionModelSerializer(NamedModelSerializer):
    """A common class for BrowserCollectionModels."""

    class Meta(NamedModelSerializer.Meta):
        """Abstract class."""

        abstract = True


class PublisherSerializer(CollectionModelSerializer):
    """Publisher Model."""

    class Meta(CollectionModelSerializer.Meta):
        """Configure model."""

        model = Publisher


class ImprintSerializer(CollectionModelSerializer):
    """Imprint Model."""

    class Meta(CollectionModelSerializer.Meta):
        """Configure model."""

        model = Imprint


class SeriesSerializer(CollectionModelSerializer):
    """Series Model."""

    class Meta(CollectionModelSerializer.Meta):
        """Configure model."""

        model = Series


class VolumeSerializer(CollectionModelSerializer):
    """Volume Model."""

    class Meta(CollectionModelSerializer.Meta):
        """Configure model."""

        model = Volume
