"""PWA views."""

from codex.views.template import CodexTemplateView


class WebManifestView(CodexTemplateView):
    """Serve the webmanifest spec."""

    template_name = "pwa/manifest.webmanifest"
    content_type = "application/manifest+json"


class ServiceWorkerRegisterView(CodexTemplateView):
    """Serve the serviceworker register javascript."""

    template_name = "pwa/serviceworker-register.js"
    content_type = "application/javascript"


class ServiceWorkerView(CodexTemplateView):
    """Serve the serviceworker javascript."""

    template_name = "pwa/serviceworker.js"
    content_type = "application/javascript"
