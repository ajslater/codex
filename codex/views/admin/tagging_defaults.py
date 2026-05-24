"""Admin Comicbox Tagging Defaults View."""

from rest_framework.response import Response

from codex.models import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import ComicboxTaggingDefaultsSerializer
from codex.views.admin.auth import AdminAPIView


class AdminTaggingDefaultsView(AdminAPIView):
    """GET/PUT for the ComicboxTaggingDefaults singleton."""

    def get(self, _request):
        """Return the current tagging defaults."""
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        serializer = ComicboxTaggingDefaultsSerializer(defaults)
        return Response(serializer.data)

    def put(self, request):
        """Update the tagging defaults."""
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        serializer = ComicboxTaggingDefaultsSerializer(
            defaults, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ComicboxTaggingDefaultsSerializer(defaults).data)
