"""Admin group serializers."""

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
        fields = ("pk", "name", "library_set", "user_set", "exclude")
        read_only_fields = ("pk",)

    def update(self, instance, validated_data):
        """Update with nested GroupAuth."""
        exclude = validated_data.pop("groupauth", {}).get("exclude")
        if exclude is not None:
            groupauth = GroupAuth.objects.get(group=instance)
            groupauth.exclude = exclude
            groupauth.save()
        return super().update(instance, validated_data)

    def create(self, validated_data):
        """Create with nested GroupAuth."""
        exclude = validated_data.pop("groupauth", {}).get("exclude", False)
        instance = super().create(validated_data)
        GroupAuth.objects.create(group=instance, exclude=exclude)
        return instance
