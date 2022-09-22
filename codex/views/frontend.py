"""Frontend views."""
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.views.session import BrowserSessionViewBase


class IndexView(BrowserSessionViewBase):
    """The main app."""

    renderer_classes = [TemplateHTMLRenderer]
    template_name = "index.html"
    main_urls = {}

    def get(self, request, *args, **kwargs):
        """Get the app index page."""
        extra_context = {
            "last_route": self.get_from_session("route"),
        }
        return Response(extra_context)
