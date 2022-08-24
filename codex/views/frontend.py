"""Frontend views."""
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.settings.settings import DEBUG
from codex.views.session import BrowserSessionViewBase


class IndexView(BrowserSessionViewBase):
    """The main app."""

    renderer_classes = [TemplateHTMLRenderer]
    template_name = "index.html"

    def get(self, request, *args, **kwargs):
        extra_context = {"last_route": self.get_from_session("route"), "DEBUG": DEBUG}
        return Response(extra_context)
