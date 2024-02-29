"""Frontend views."""

from typing import ClassVar

from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.views.session import BrowserSessionViewBase


class IndexView(BrowserSessionViewBase):
    """The main app."""

    renderer_classes: ClassVar[list] = [TemplateHTMLRenderer]  # type: ignore
    template_name = "index.html"

    def get(self, *_args, **_kwargs):
        """Get the app index page."""
        last_route = self.get_from_session("route")
        extra_context = {"last_route": last_route}
        return Response(extra_context)
