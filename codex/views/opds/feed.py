"""OPDS Browser View."""

from collections.abc import Sequence

from rest_framework.throttling import BaseThrottle, ScopedRateThrottle

from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.settings import OPDSBrowserSettingsMixin


class OPDSBrowserView(OPDSBrowserSettingsMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    def __init__(self, *args, **kwargs) -> None:
        """Add User Agent Name."""
        super().__init__(*args, **kwargs)
        self._user_agent_name = None
