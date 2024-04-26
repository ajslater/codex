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
        last_pks = last_route.get("pks")
        last_pks_str = ",".join(str(pk) for pk in last_pks) if last_pks else "0"
        last_route["pks"] = last_pks_str
        extra_context = {"last_route": last_route}
        return Response(extra_context)
