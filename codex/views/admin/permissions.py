"""Codex drf permissions."""

from typing import override

from rest_framework.permissions import BasePermission, IsAdminUser

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag


class HasAPIKeyOrIsAdminUser(BasePermission):
    """Does the request have the current api key."""

    @override
    def has_permission(self, request, view) -> bool:
        """Test the request api key against the database."""
        data = request.GET if request.method == "GET" else request.POST
        api_key = data.get("apiKey")
        if not api_key:
            return IsAdminUser().has_permission(request, view)
        return AdminFlag.objects.filter(
            key=AdminFlagChoices.API_KEY.value, value=api_key
        ).exists()
