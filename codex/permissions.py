"""Codex drf permissions."""
from rest_framework.permissions import BasePermission, IsAdminUser

from codex.models import Timestamp


class HasAPIKeyOrIsAdminUser(BasePermission):
    """Does the request have the current api key."""

    def has_permission(self, request, view):
        """Test the request api key against the database."""
        if request.method == "GET":
            data = request.GET
        else:
            data = request.POST
        key = data.get("apiKey")
        if not key:
            return IsAdminUser().has_permission(request, view)
        return Timestamp.objects.filter(name=Timestamp.API_KEY, version=key).exists()
