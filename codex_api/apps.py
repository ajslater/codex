"""App Config."""

from logging import getLogger

from django.apps import AppConfig


LOG = getLogger(__name__)


class CodexAPIConfig(AppConfig):
    """Application config, mostly for startup tasks."""

    name = "codex_api"
    verbose_name = "Codex API"

    def ready(self):
        """Do this once when the app is ready."""
        self.get_model("AdminFlag").init_all_flags()
