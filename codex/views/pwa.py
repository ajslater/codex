"""PWA views."""
from django.views.generic import TemplateView


class WebManifestView(TemplateView):
    """Serve the webmanifest spec."""

    template_name = "pwa/manifest.webmanifest"
    content_type = "application/manifest+json"


class ServiceWorkerRegisterView(TemplateView):
    """Serve the serviceworker register javascript."""

    template_name = "pwa/serviceworkerRegister.js"
    content_type = "application/javascript"


class ServiceWorkerView(TemplateView):
    """Serve the serviceworker javascript."""

    template_name = "pwa/serviceworker.js"
    content_type = "application/javascript"
