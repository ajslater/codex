"""Frontend views."""

from collections.abc import Sequence

from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.renderers import BaseRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict

from codex.serializers.route import RouteSerializer
from codex.views.browser.settings import BrowserSettingsBaseView
from codex.views.mixins import UserActiveMixin


class IndexView(BrowserSettingsBaseView, UserActiveMixin):
    """The main app."""

    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    renderer_classes: Sequence[type[BaseRenderer]] = [TemplateHTMLRenderer]
    template_name = "index.html"

    def _get_last_route(self) -> ReturnDict:
        """Get the last route from the session."""
        last_route = self.get_last_route()
        serializer = RouteSerializer(last_route)
        return serializer.data

    def get(self, *_args, **_kwargs) -> Response:
        """Get the app index page."""
        extra_context = {
            "last_route": self._get_last_route(),
        }
        self.mark_user_active()
        return Response(extra_context)
