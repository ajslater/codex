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
        last_route = self.get_last_route(serialize=True)
        last_route.pop("name", None)
        extra_context = {"last_route": last_route}
        return Response(extra_context)
