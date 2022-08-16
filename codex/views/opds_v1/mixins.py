"""OPDS basic authentication."""
from django.http.response import HttpResponse
from rest_framework.authentication import BasicAuthentication
from rest_framework.views import APIView

from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers


LOG = get_logger(__name__)


class OPDSAuthenticationMixin(APIView):
    """OPDS Authentication."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def _authenticate(self, request):
        """Authenticate using basic authentiaction and then DRF permissions."""
        if not request.user or not request.user.is_authenticated:
            # Use Basic Auth from DRF
            user_auth_tuple = BasicAuthentication().authenticate(request)
            if user_auth_tuple is not None:
                request.user, _ = user_auth_tuple

        # Copy of DRF permission checker for wsgi requests
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                message = getattr(permission, "message", None)
                code = getattr(permission, "code", 404)
                return HttpResponse(reason=message, status=code)
