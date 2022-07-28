"""Frontend views."""
from django.urls import get_script_prefix
from django.views.generic import TemplateView

from codex.settings.settings import DEBUG
from codex.views.session import SessionView


class IndexView(SessionView, TemplateView):
    """The main app."""

    SESSION_KEY = SessionView.BROWSER_KEY

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        """Add extra context to the template."""
        context = super().get_context_data(**kwargs)
        context["last_route"] = self.get_from_session("route")
        context["script_prefix"] = get_script_prefix()
        context["DEBUG"] = DEBUG
        return context
