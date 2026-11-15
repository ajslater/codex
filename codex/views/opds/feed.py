"""OPDS Browser View."""

from collections.abc import Sequence

from rest_framework.throttling import BaseThrottle

from codex.models.shelf import Shelf
from codex.throttling import ScopedRateThrottle
from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.settings import OPDSBrowserSettingsMixin


class OPDSBrowserView(OPDSBrowserSettingsMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    def user_shelves(self) -> tuple[tuple[int, str], ...]:
        """
        Return ``(pk, name)`` for each non-empty shelf of the requesting user.

        Ordered by name. Empty for anonymous sessions, who own no shelves.
        The v1 and v2 start pages both build their shelf entries from this.
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return ()
        return tuple(
            Shelf.objects.filter(user=user, items__isnull=False)
            .distinct()
            .order_by("name", "pk")
            .values_list("pk", "name")
        )
