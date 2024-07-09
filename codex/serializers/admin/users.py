"""User serializers."""

from django.contrib.auth.models import User
from rest_framework.serializers import (
    CharField,
    DateTimeField,
    Serializer,
)

from codex.serializers.models.base import BaseModelSerializer


class UserChangePasswordSerializer(Serializer):
    """Special User Change Password Serializer."""

    password = CharField(write_only=True)


class UserSerializer(BaseModelSerializer, UserChangePasswordSerializer):
    """User Serializer."""

    last_active = DateTimeField(
        read_only=True, source="useractive.updated_at", allow_null=True
    )

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = User
        fields = (
            "pk",
            "username",
            "password",
            "groups",
            "is_staff",
            "is_active",
            "last_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("pk", "last_active", "last_login", "date_joined")
