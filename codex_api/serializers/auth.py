"""Codex Auth Serializers."""

from django.contrib.auth.models import User
from django.urls import reverse_lazy
from rest_framework.fields import BooleanField
from rest_framework.fields import CharField
from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import Serializer


class UserSerializer(ModelSerializer):
    """Serialize User model for UI."""

    adminURL = CharField(default=reverse_lazy("admin:index"))  # noqa: N815

    class Meta:
        """Model spec."""

        model = User
        fields = ("pk", "username", "is_staff", "adminURL")
        read_only_fields = fields


class TimezoneSerializer(Serializer):
    """Serialize Timezone submission from front end."""

    timezone = CharField(min_length=2)


class UserCreateSerializer(ModelSerializer, TimezoneSerializer):
    """Serialize registration input for creating users."""

    class Meta:
        """Model spec."""

        model = User
        fields = ("username", "password")
        extra_kwargs = {"password": {"write_only": True}}


class UserLoginSerializer(UserCreateSerializer):
    """Serialize user login input."""

    # specificy this so it doesn't trigger the username unique constraint.
    username = CharField(min_length=2)


class RegistrationEnabledSerializer(Serializer):
    """Serialize one admin flag."""

    enableRegistration = BooleanField(read_only=True)  # noqa: N815
