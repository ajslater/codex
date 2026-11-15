"""
Device key management views.

A device key is a named credential for one reader app or device, valid on
OPDS and KOReader sync only. These views live under ``/api/v4/auth/``,
which keeps the default DRF authentication classes: a device key does not
authenticate here, so a key cannot list, create or revoke keys.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from loguru import logger
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.models.api_key import UserApiKey
from codex.serializers.device_keys import DeviceKeyNameSerializer
from codex.views.auth import AuthGenericAPIView

_DUPLICATE_NAME = "You already have a device key with that name."


def _key_repr(api_key: UserApiKey) -> dict:
    """Return the listed shape of a key, never the key or its hashes."""
    return {
        "pk": api_key.pk,
        "name": api_key.name,
        "prefix": api_key.prefix,
        "created_at": api_key.created_at,
        "last_used_at": api_key.last_used_at,
    }


class _DeviceKeyAuthView(AuthGenericAPIView):
    """Authenticated-only base scoped to the requesting user's keys."""

    permission_classes = (IsAuthenticated,)
    serializer_class = DeviceKeyNameSerializer

    def _get_key(self) -> UserApiKey | None:
        """
        Return the requesting user's key for the url pk, or None.

        Another user's key is indistinguishable from a missing one.
        """
        return UserApiKey.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
        ).first()

    def _validated_name(self) -> str:
        serializer = DeviceKeyNameSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["name"]

    @staticmethod
    def _error(detail: str) -> Response:
        return Response({"detail": detail}, status=400)


class DeviceKeyListView(_DeviceKeyAuthView):
    """GET: the user's device keys. POST: create one."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{keys: [{pk, name, prefix, created_at, last_used_at}]}``."""
        keys = UserApiKey.objects.filter(user=self.request.user).order_by("name", "pk")
        return Response({"keys": [_key_repr(api_key) for api_key in keys]})

    def post(self, *_args, **_kwargs) -> Response:
        """Create a key. The response is the only time the key is returned."""
        name = self._validated_name()
        user = self.request.user
        if UserApiKey.objects.filter(user=user, name=name).exists():
            return self._error(_DUPLICATE_NAME)
        try:
            api_key, key = UserApiKey.create_for_user(user, name)
        except ValidationError as exc:
            return self._error(" ".join(exc.messages))
        except IntegrityError:
            # Lost a race with an identical create.
            return self._error(_DUPLICATE_NAME)
        logger.info(f"Device key created for user {user}")
        return Response({**_key_repr(api_key), "key": key}, status=201)


class DeviceKeyDetailView(_DeviceKeyAuthView):
    """PATCH: rename a key. DELETE: revoke it."""

    def patch(self, *_args, **_kwargs) -> Response:
        """Rename the key."""
        api_key = self._get_key()
        if api_key is None:
            return Response(status=404)
        name = self._validated_name()
        if name != api_key.name:
            clash = UserApiKey.objects.filter(
                user=self.request.user, name=name
            ).exclude(pk=api_key.pk)
            if clash.exists():
                return self._error(_DUPLICATE_NAME)
            api_key.name = name
            try:
                api_key.save(update_fields=("name", "updated_at"))
            except IntegrityError:
                return self._error(_DUPLICATE_NAME)
        return Response(_key_repr(api_key))

    def delete(self, *_args, **_kwargs) -> Response:
        """Revoke the key. Idempotent."""
        deleted, _ = UserApiKey.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
        ).delete()
        if deleted:
            logger.info(f"Device key revoked for user {self.request.user}")
        return Response(status=204)
