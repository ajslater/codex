"""Admin flag serializers."""

from codex.models import AdminFlag
from codex.serializers.models.base import BaseModelSerializer


class AdminFlagSerializer(BaseModelSerializer):
    """Admin Flag Serializer."""

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = AdminFlag
        fields = ("key", "on")
        read_only_fields = ("key",)
