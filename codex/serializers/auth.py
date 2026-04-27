"""Codex Auth Serializers."""

from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import (
    Serializer,
    SerializerMetaclass,
)

from codex.serializers.fields.auth import TimezoneField


class TimezoneSerializerMixin(metaclass=SerializerMetaclass):
    """Serialize Timezone submission from front end."""

    timezone = TimezoneField(write_only=True)


class TimezoneSerializer(TimezoneSerializerMixin, Serializer):
    """Serialize Timezone submission from front end."""


class AuthAdminFlagsSerializer(Serializer):
    """Admin flags related to auth."""

    banner_text = CharField(read_only=True)
    lazy_import_metadata = BooleanField(read_only=True)
    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
