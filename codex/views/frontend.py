"""Frontend views."""

from typing import ClassVar

from rest_framework.permissions import AllowAny
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.serializers.route import RouteSerializer
from codex.views.session import SessionView


class IndexView(SessionView):
    """The main app."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    permission_classes = (AllowAny,)
    renderer_classes: ClassVar[list] = [TemplateHTMLRenderer]  # type: ignore
    template_name = "index.html"

    def get(self, *_args, **_kwargs):
        """Get the app index page."""
        last_route = self.get_last_route(name=False)
        serializer = RouteSerializer(last_route)
        last_route = serializer.data
        extra_context = {"last_route": last_route}
        return Response(extra_context)
