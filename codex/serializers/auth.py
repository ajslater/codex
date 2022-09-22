"""Codex Auth Serializers."""

from django.contrib.auth.models import User
from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import (
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)

from codex.models import AdminFlag


class UserSerializer(ModelSerializer):
    """Serialize User model for UI."""

    _ADMIN_FLAG_NAMES = (AdminFlag.ENABLE_NON_USERS, AdminFlag.ENABLE_REGISTRATION)

    admin_flags = SerializerMethodField()

    def get_admin_flags(self, obj):
        """Piggyback admin flags on the user object."""
        flags = AdminFlag.objects.filter(name__in=self._ADMIN_FLAG_NAMES).values(
            "name", "on"
        )
        admin_flags = {}
        for flag in flags:
            name = flag["name"]
            key = name[0].lower() + name[1:].replace(" ", "")
            admin_flags[key] = flag["on"]
        return admin_flags

    class Meta:
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


class UserCreateSerializer(ModelSerializer, TimezoneSerializer):
    """Serialize registration input for creating users."""

    class Meta:
        """Model spec."""

        model = User
        fields = ("username", "password", "timezone")
        extra_kwargs = {"password": {"write_only": True}}


class UserLoginSerializer(UserCreateSerializer):
    """Serialize user login input."""

    # specify this so it doesn't trigger the username unique constraint.
    username = CharField(min_length=2)

    class Meta(UserCreateSerializer.Meta):
        """Explicit meta inheritance required."""


class RegistrationEnabledSerializer(Serializer):
    """Serialize one admin flag."""

    enable_registration = BooleanField(read_only=True)


class AuthAdminFlagsSerializer(Serializer):
    """Admin flags related to auth."""

    enable_non_users = BooleanField(read_only=True)
    enable_registration = BooleanField(read_only=True)
