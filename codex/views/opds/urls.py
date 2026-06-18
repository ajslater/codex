"""OPDS URLs API for popup."""

from django.urls import reverse
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.serializers.opds.urls import OPDSURLsSerializer
from codex.views.auth import AuthGenericAPIView

_OPDS_VERSIONS = (1, 2)


class OPDSURLsView(AuthGenericAPIView):
    """OPDS URLs."""

    serializer_class: type[BaseSerializer] | None = OPDSURLsSerializer

    def get(self, *args, **kwargs) -> Response:
        """Resolve the urls."""
        # The start routes carry no path params (the catalog root); the
        # ``?page=`` default is implicit, so reverse needs no kwargs.
        obj = {
            f"v{version}": reverse(f"opds:v{version}:start")
            for version in _OPDS_VERSIONS
        }
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
