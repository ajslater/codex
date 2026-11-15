"""OPDS Browser View."""

from collections.abc import Sequence

from rest_framework.throttling import BaseThrottle

from codex.models.favorite import Favorite
from codex.throttling import ScopedRateThrottle
from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.settings import OPDSBrowserSettingsMixin


class OPDSBrowserView(OPDSBrowserSettingsMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    def user_has_favorites(self) -> bool:
        """Return True when the requesting user has at least one favorite."""
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        return Favorite.objects.filter(user=user).exists()
