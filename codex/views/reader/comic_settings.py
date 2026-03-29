"""Per-comic reader settings view."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models.settings import ClientChoices, SettingsReader
from codex.serializers.reader import ReaderSettingsSerializer
from codex.views.auth import AuthGenericAPIView
from codex.views.bookmark import BookmarkAuthMixin


class ReaderComicSettingsView(BookmarkAuthMixin, AuthGenericAPIView):
    """Get and update per-comic reader settings."""

    serializer_class: type[BaseSerializer] | None = ReaderSettingsSerializer

    def _get_or_create_comic_settings(self) -> SettingsReader:
        """Get or create SettingsReader for this user/session + comic."""
        auth_filter = self.get_bookmark_auth_filter()
        comic_pk = self.kwargs["pk"]
        client = ClientChoices.API

        lookup = {"client": client, "comic_id": comic_pk, **auth_filter}
        instance = SettingsReader.objects.filter(**lookup).first()
        if instance is not None:
            return instance

        return SettingsReader.objects.create(**lookup)

    @staticmethod
    def _instance_to_dict(instance: SettingsReader) -> dict:
        """Convert a SettingsReader to a dict for the serializer."""
        return {key: getattr(instance, key) for key in instance.DIRECT_KEYS}

    @extend_schema(responses=ReaderSettingsSerializer)
    def get(self, *args, **kwargs) -> Response:
        """Get per-comic reader settings."""
        instance = self._get_or_create_comic_settings()
        data = self._instance_to_dict(instance)
        serializer = self.get_serializer(data)
        return Response(serializer.data)

    @extend_schema(request=ReaderSettingsSerializer, responses=ReaderSettingsSerializer)
    def patch(self, *args, **kwargs) -> Response:
        """Update per-comic reader settings."""
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        instance = self._get_or_create_comic_settings()
        for key, value in serializer.validated_data.items():
            if key in instance.DIRECT_KEYS:
                setattr(instance, key, value)
        instance.save()

        data = self._instance_to_dict(instance)
        serializer = self.get_serializer(data)
        return Response(serializer.data)
