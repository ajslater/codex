"""Browser Group Model Serializers."""

from codex.models import (
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.serializers.models.named import NamedModelSerializer


class GroupModelSerializer(NamedModelSerializer):
    """A common class for BrowserGroupModels."""

    class Meta(NamedModelSerializer.Meta):
        """Abstract class."""

        abstract = True


class PublisherSerializer(GroupModelSerializer):
    """Publisher Model."""

    class Meta(GroupModelSerializer.Meta):
        """Configure model."""

        model = Publisher


class ImprintSerializer(GroupModelSerializer):
    """Imprint Model."""

    class Meta(GroupModelSerializer.Meta):
        """Configure model."""

        model = Imprint


class SeriesSerializer(GroupModelSerializer):
    """Series Model."""

    class Meta(GroupModelSerializer.Meta):
        """Configure model."""

        model = Series
        # fields = (*NamedModelMeta.fields, "volume_count")


class VolumeSerializer(GroupModelSerializer):
    """Volume Model."""

    class Meta(GroupModelSerializer.Meta):
        """Configure model."""

        model = Volume
        # fields = (*NamedModelMeta.fields, "issue_count")
