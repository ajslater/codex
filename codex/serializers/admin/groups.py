"""Admin group serializers."""

from typing import Any, override

from django.contrib.auth.models import Group
from rest_framework.serializers import (
    BooleanField,
    CharField,
)

from codex.models.admin import GroupAuth
from codex.serializers.models.base import BaseModelSerializer


class GroupSerializer(BaseModelSerializer):
    """Group Serialier."""

    exclude = BooleanField(default=False, source="groupauth.exclude")
    metron_age_rating = CharField(
        allow_null=True,
        required=False,
        source="groupauth.metron_age_rating",
    )

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = Group
        fields = (
            "pk",
            "name",
            "library_set",
            "user_set",
            "exclude",
            "metron_age_rating",
        )
        read_only_fields = ("pk",)

    @staticmethod
    def _apply_groupauth(instance, groupauth_data) -> None:
        """Apply nested GroupAuth fields in one pass."""
        if not groupauth_data:
            return
        groupauth = GroupAuth.objects.get(group=instance)
        update_fields = []
        for field in ("exclude", "metron_age_rating"):
            if field in groupauth_data:
                setattr(groupauth, field, groupauth_data[field])
                update_fields.append(field)
        if update_fields:
            groupauth.save(update_fields=update_fields)

    @override
    def update(self, instance, validated_data) -> Any:
        """Update with nested GroupAuth."""
        groupauth_data = validated_data.pop("groupauth", {})
        self._apply_groupauth(instance, groupauth_data)
        return super().update(instance, validated_data)

    @override
    def create(self, validated_data) -> Any:
        """Create with nested GroupAuth."""
        groupauth_data = validated_data.pop("groupauth", {})
        instance = super().create(validated_data)
        GroupAuth.objects.create(
            group=instance,
            exclude=groupauth_data.get("exclude", False),
            metron_age_rating=groupauth_data.get("metron_age_rating"),
        )
        return instance
