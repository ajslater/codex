"""
API key management views.

``/api/v4/auth/keys`` lists, creates, renames and revokes the requesting
user's API keys, of every scope. These views keep the default DRF
authentication classes, where only a universal key logs in: a device or
stats key cannot list, create or revoke keys.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from loguru import logger
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from codex.choices.api_key import ApiKeyScope
from codex.models.api_key import UserApiKey
from codex.serializers.api_keys import ApiKeyCreateSerializer, ApiKeyNameSerializer
from codex.views.auth import AuthGenericAPIView

_DUPLICATE_NAME = "You already have an API key with that name."
_STAFF_ONLY = "Only admins can make Stats API keys."
_UNIVERSAL_RENAME = "A Universal Token cannot be renamed."


def _key_repr(api_key: UserApiKey) -> dict:
    """Return the listed shape of a key, never the key or its hashes."""
    return {
        "pk": api_key.pk,
        "name": api_key.name,
        "scope": api_key.scope,
        "prefix": api_key.prefix,
        "created_at": api_key.created_at,
        "last_used_at": api_key.last_used_at,
    }


class _ApiKeyAuthView(AuthGenericAPIView):
    """Authenticated-only base scoped to the requesting user's keys."""

    permission_classes = (IsAuthenticated,)
    serializer_class = ApiKeyNameSerializer

    def _get_key(self) -> UserApiKey | None:
        """
        Return the requesting user's key for the url pk, or None.

        Another user's key is indistinguishable from a missing one.
        """
        return UserApiKey.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
        ).first()

    def _validated(self, serializer_class) -> dict:
        serializer = serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def _error(detail: str, status: int = 400) -> Response:
        return Response({"detail": detail}, status=status)


class ApiKeyListView(_ApiKeyAuthView):
    """GET: the user's API keys. POST: create one."""

    serializer_class = ApiKeyCreateSerializer

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{keys: [{pk, name, scope, prefix, created_at, last_used_at}]}``."""
        keys = UserApiKey.objects.filter(user=self.request.user).order_by("name", "pk")
        return Response({"keys": [_key_repr(api_key) for api_key in keys]})

    def post(self, *_args, **_kwargs) -> Response:
        """Create a key. The response is the only time the key is returned."""
        data = self._validated(ApiKeyCreateSerializer)
        name = data["name"]
        scope = data["scope"]
        user = self.request.user
        is_staff = IsAdminUser().has_permission(self.request, self)
        if scope == ApiKeyScope.STATS.value and not is_staff:
            return self._error(_STAFF_ONLY, status=403)
        if UserApiKey.objects.filter(user=user, name=name).exists():
            return self._error(_DUPLICATE_NAME)
        try:
            api_key, key = UserApiKey.create_for_user(user, name, scope)
        except ValidationError as exc:
            return self._error(" ".join(exc.messages))
        except IntegrityError:
            # Lost a race with an identical create.
            return self._error(_DUPLICATE_NAME)
        label = ApiKeyScope(api_key.scope).label
        logger.info(f"{label} API key created for user {user}")
        return Response({**_key_repr(api_key), "key": key}, status=201)


class ApiKeyDetailView(_ApiKeyAuthView):
    """PATCH: rename a key. DELETE: revoke it."""

    def patch(self, *_args, **_kwargs) -> Response:
        """Rename the key."""
        api_key = self._get_key()
        if api_key is None:
            return Response(status=404)
        if api_key.scope == ApiKeyScope.UNIVERSAL.value:
            return self._error(_UNIVERSAL_RENAME)
        name = self._validated(ApiKeyNameSerializer)["name"]
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
        """Revoke the key, of any scope. Idempotent."""
        deleted, _ = UserApiKey.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
        ).delete()
        if deleted:
            logger.info(f"API key revoked for user {self.request.user}")
        return Response(status=204)
