"""User serializers."""

from typing import Any, override

from django.contrib.auth.models import User
from rest_framework.serializers import (
    CharField,
    DateTimeField,
    PrimaryKeyRelatedField,
    Serializer,
    SerializerMetaclass,
)

from codex.models import AgeRatingMetron
from codex.models.auth import UserAuth
from codex.serializers.models.base import BaseModelSerializer


class PasswordSerializerMixin(metaclass=SerializerMetaclass):
    """Password Serializer Mixin."""

    password = CharField(write_only=True)


class UserChangePasswordSerializer(Serializer, PasswordSerializerMixin):
    """Special User Change Password Serializer."""


class UserSerializer(BaseModelSerializer, PasswordSerializerMixin):
    """User Serializer."""

    password = CharField(write_only=True, required=False, allow_blank=True)
    last_active = DateTimeField(
        read_only=True, source="userauth.updated_at", allow_null=True
    )
    age_rating_metron = PrimaryKeyRelatedField(
        queryset=AgeRatingMetron.objects.all(),
        source="userauth.age_rating_metron",
        allow_null=True,
        required=False,
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
            "age_rating_metron",
        )
        read_only_fields = ("pk", "last_active", "last_login", "date_joined")

    @staticmethod
    def _apply_userauth(instance, userauth_data) -> None:
        """
        Apply nested :class:`UserAuth` fields with a single ``UPDATE``.

        :class:`UserAuth` rows are created by
        :meth:`AdminUserViewSet.perform_create` on user creation, so the
        row is guaranteed to exist on update. ``filter().update()`` is
        one round trip vs ``get_or_create`` + ``save`` — and a missing
        auth row stays a no-op rather than re-creating a default one
        (which would mask a data-integrity issue from the create path).
        """
        if not userauth_data or "age_rating_metron" not in userauth_data:
            return
        UserAuth.objects.filter(user=instance).update(
            age_rating_metron=userauth_data["age_rating_metron"],
        )

    @override
    def update(self, instance, validated_data) -> Any:
        """Update with nested UserAuth."""
        userauth_data = validated_data.pop("userauth", {})
        self._apply_userauth(instance, userauth_data)
        return super().update(instance, validated_data)
