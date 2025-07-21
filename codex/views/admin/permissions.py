"""Codex drf permissions."""

from rest_framework.permissions import BasePermission, IsAdminUser
from typing_extensions import override

from codex.models import Timestamp


class HasAPIKeyOrIsAdminUser(BasePermission):
    """Does the request have the current api key."""

    @override
    def has_permission(self, request, view):
        """Test the request api key against the database."""
        data = request.GET if request.method == "GET" else request.POST
        api_key = data.get("apiKey")
        if not api_key:
            return IsAdminUser().has_permission(request, view)
        return Timestamp.objects.filter(
            key=Timestamp.Choices.API_KEY.value, version=api_key
        ).exists()
