"""Frontend views."""
from django.views.generic import TemplateView

from codex.settings.settings import DEBUG
from codex.views.session import SessionViewBase


class IndexView(TemplateView, SessionViewBase):
    """The main app."""

    SESSION_KEY = SessionViewBase.BROWSER_KEY

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        """Add extra context to the template."""
        context = super().get_context_data(**kwargs)
        context["last_route"] = self.get_from_session("route")
        context["DEBUG"] = DEBUG
        return context
