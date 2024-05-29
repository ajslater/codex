"""Codex drf permissions."""

from rest_framework.permissions import BasePermission, IsAdminUser

from codex.models import Timestamp


class HasAPIKeyOrIsAdminUser(BasePermission):
    """Does the request have the current api key."""

    def has_permission(self, request, view):  # type: ignore
        """Test the request api key against the database."""
        data = request.GET if request.method == "GET" else request.POST
        api_key = data.get("apiKey")
        if not api_key:
            return IsAdminUser().has_permission(request, view)
        return Timestamp.objects.filter(
            key=Timestamp.TimestampChoices.API_KEY.value, version=api_key
        ).exists()
