"""PWA views."""
from django.urls import get_script_prefix
from django.views.generic import TemplateView

from codex.settings.settings import DEBUG


class PWAView(TemplateView):
    """Add script prefix to the template variables."""

    def get_context_data(self, **kwargs):
        """Add extra context to the template."""
        context = super().get_context_data(**kwargs)
        context["script_prefix"] = get_script_prefix()
        context["DEBUG"] = DEBUG
        return context


class WebManifestView(PWAView):
    """Serve the webmanifest spec."""

    template_name = "pwa/manifest.webmanifest"
    content_type = "application/manifest+json"


class ServiceWorkerRegisterView(PWAView):
    """Serve the serviceworker register javascript."""

    template_name = "pwa/serviceworkerRegister.js"
    content_type = "application/javascript"


class ServiceWorkerView(PWAView):
    """Serve the serviceworker javascript."""

    template_name = "pwa/serviceworker.js"
    content_type = "application/javascript"


class OfflineView(PWAView):
    """Serve the offline page."""

    template_name = "pwa/offline.html"
