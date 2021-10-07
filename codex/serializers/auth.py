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

    enableNonUsers = SerializerMethodField()  # noqa: N815

    def get_enableNonUsers(self, obj):  # noqa: N802
        """Piggyback on user objects. A little awkward."""
        enu_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_NON_USERS)
        return enu_flag.on

    class Meta:
        """Model spec."""

        model = User
        fields = ("pk", "username", "is_staff", "enableNonUsers")
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

    enableRegistration = BooleanField(read_only=True)  # noqa: N815
