"""Admin flag serializers."""

from rest_framework.serializers import PrimaryKeyRelatedField

from codex.models import AdminFlag, AgeRatingMetron
from codex.serializers.models.base import BaseModelSerializer


class AdminFlagSerializer(BaseModelSerializer):
    """Admin Flag Serializer."""

    # The two age-rating flags (``AR`` / ``AA``) use this FK; other
    # flags leave it NULL and stick with ``on`` / ``value``.
    age_rating_metron = PrimaryKeyRelatedField(
        queryset=AgeRatingMetron.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = AdminFlag
        fields = ("key", "on", "value", "age_rating_metron")
        read_only_fields = ("key",)
