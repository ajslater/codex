"""Frontend views."""
import json

from django.contrib.staticfiles.storage import staticfiles_storage
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from codex.settings.settings import DEBUG, STATIC_ROOT
from codex.views.session import BrowserSessionViewBase


class IndexView(BrowserSessionViewBase):
    """The main app."""

    renderer_classes = [TemplateHTMLRenderer]
    template_name = "index.html"
    main_urls = {}

    @classmethod
    def load_main_urls(cls):
        """Load production asset urls from the manifest."""
        manifest_path = STATIC_ROOT / staticfiles_storage.stored_name("manifest.json")
        with manifest_path.open("r") as manifest_file:
            manifest = json.load(manifest_file)

        cls.main_urls = {
            "main_js": manifest["src/main.js"]["file"],
            "main_css": manifest["src/main.css"]["file"],
        }

    def get(self, request, *args, **kwargs):
        """Get the app index page."""
        extra_context = {
            "DEBUG": DEBUG,
            "last_route": self.get_from_session("route"),
        }
        if not DEBUG:
            if not self.main_urls:
                self.load_main_urls()
            extra_context = {**extra_context, **self.main_urls}

        return Response(extra_context)
