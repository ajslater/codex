"""Admin Model Serializers."""

from codex.models.admin import LibrarianStatus
from codex.serializers.models.base import BaseModelSerializer


class LibrarianStatusSerializer(BaseModelSerializer):
    """Serializer Librarian task statuses."""

    class Meta(BaseModelSerializer.Meta):
        """Configure the model."""

        model = LibrarianStatus
        exclude = ("active", "created_at", "updated_at")
