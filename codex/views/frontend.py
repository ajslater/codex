"""Frontend views."""
from django.shortcuts import render
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


def webmanifest(request):
    """Serve the webmanifest spec. For android and chrome."""
    return render(request, "site.webmanifest", content_type="application/manifest+json")


def browserconfig(request):
    """Serve browserconfig xml for microsoft."""
    return render(request, "browserconfig.xml", content_type="text/xml")
