"""Frontend views."""

from typing import ClassVar

from rest_framework.permissions import AllowAny
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.models.admin import AdminFlag
from codex.serializers.route import RouteSerializer
from codex.views.session import SessionView


class IndexView(SessionView):
    """The main app."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    permission_classes = (AllowAny,)
    renderer_classes: ClassVar[list] = [TemplateHTMLRenderer]  # type: ignore[reportIncompatibleVariableOverride]
    template_name = "index.html"

    def _get_last_route(self):
        """Get the last route from the session."""
        last_route = self.get_last_route(name=False)
        serializer = RouteSerializer(last_route)
        return serializer.data

    def _get_title(self):
        """Get the title from the banner text."""
        bt_flag = AdminFlag.objects.get(key="BT")
        title = "Codex"
        if bt_flag.value:
            title = bt_flag.value + " - " + title
        return title

    def get(self, *_args, **_kwargs):
        """Get the app index page."""
        extra_context = {
            "last_route": self._get_last_route(),
            "title": self._get_title(),
        }
        return Response(extra_context)
