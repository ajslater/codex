"""Codex Auth Serializers."""

from django.contrib.auth.models import User
from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import (
    Serializer,
    SerializerMethodField,
)

from codex.models import AdminFlag
from codex.serializers.models.base import BaseModelSerializer


class UserSerializer(BaseModelSerializer):
    """Serialize User model for UI."""

    _ADMIN_FLAG_KEYS = (
        AdminFlag.FlagChoices.NON_USERS.value,
        AdminFlag.FlagChoices.REGISTRATION.value,
    )

    admin_flags = SerializerMethodField()

    def get_admin_flags(self, *_args):
        """Piggyback admin flags on the user object."""
        flags = AdminFlag.objects.filter(key__in=self._ADMIN_FLAG_KEYS).values(
            "name", "on"
        )
        admin_flags = {}
        for flag in flags:
            name = flag["name"]
            key = name[0].lower() + name[1:].replace(" ", "")
            admin_flags[key] = flag["on"]
        return admin_flags

    class Meta(BaseModelSerializer.Meta):
        """Model spec."""

        model = User
        fields = (
            "pk",
            "username",
            "is_staff",
            "admin_flags",
        )
        read_only_fields = fields


class TimezoneSerializer(Serializer):
    """Serialize Timezone submission from front end."""

    timezone = CharField(min_length=2)


class UserCreateSerializer(BaseModelSerializer, TimezoneSerializer):
    """Serialize registration input for creating users."""

    class Meta(BaseModelSerializer.Meta):
        """Model spec."""

        model = User
        fields = ("username", "password", "timezone")
        extra_kwargs = {"password": {"write_only": True}}  # noqa: RUF012


class UserLoginSerializer(UserCreateSerializer):
    """Serialize user login input."""

    # specify this so it doesn't trigger the username unique constraint.
    username = CharField(min_length=2)

    class Meta(UserCreateSerializer.Meta):
        """Explicit meta inheritance required."""


class AuthAdminFlagsSerializer(Serializer):
    """Admin flags related to auth."""

    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
