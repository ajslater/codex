"""Admin group serializers."""

from typing import Any, override

from django.contrib.auth.models import Group
from rest_framework.serializers import (
    BooleanField,
)

from codex.models.auth import GroupAuth
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
        """
        Apply nested :class:`GroupAuth` fields with a single ``UPDATE``.

        :class:`GroupAuth` rows are created alongside their ``Group`` in
        :meth:`GroupSerializer.create`, so the row is guaranteed to
        exist on update. ``filter().update()`` is one round trip vs the
        prior ``get`` + instance ``save``.
        """
        if not groupauth_data or "exclude" not in groupauth_data:
            return
        GroupAuth.objects.filter(group=instance).update(
            exclude=groupauth_data["exclude"],
        )

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
