"""Admin group serializers."""

from typing import Any, override

from django.contrib.auth.models import Group
from rest_framework.serializers import (
    BooleanField,
)

from codex.models.admin import GroupAuth
from codex.serializers.models.base import BaseModelSerializer


class GroupSerializer(BaseModelSerializer):
    """Group Serialier."""

    exclude = BooleanField(default=False, source="groupauth.exclude")

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = Group
        fields = (
            "pk",
            "name",
            "library_set",
            "user_set",
            "exclude",
        )
        read_only_fields = ("pk",)

    @staticmethod
    def _apply_groupauth(instance, groupauth_data) -> None:
        """Apply nested :class:`GroupAuth` fields in one pass."""
        if not groupauth_data:
            return
        groupauth = GroupAuth.objects.get(group=instance)
        if "exclude" in groupauth_data:
            groupauth.exclude = groupauth_data["exclude"]
            groupauth.save(update_fields=["exclude"])

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
        )
        return instance
