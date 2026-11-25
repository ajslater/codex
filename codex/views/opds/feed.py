"""OPDS Browser View."""

from collections.abc import MutableMapping, Sequence
from typing import Any, override

from rest_framework.throttling import BaseThrottle

from codex.models.readinglist import ReadingList
from codex.throttling import ScopedRateThrottle
from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.settings import OPDSBrowserSettingsMixin


class OPDSBrowserView(OPDSBrowserSettingsMixin, UserActiveMixin, BrowserView):
    """
    OPDS Browser View.

    An OPDS feed is a function of its URL. Its params are the factory
    defaults plus this request's validated query, never the saved settings
    row: a link must not inherit the filters, search or list an earlier
    link set, and one device's browsing must not change another's. Only the
    route is still recorded, for the ``up`` link.
    """

    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"

    @override
    def init_params(self) -> MutableMapping[str, Any]:
        """Return the factory params with this request's validated query on top."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        params = self.get_browser_factory_params()
        params.update(serializer.validated_data)
        # The stored route, so ``params`` queues a new one for the up link.
        params["last_route"] = dict(self.get_last_route())
        return params

    @override
    def save_params_to_settings(
        self, params, *, defer_last_route: bool = False
    ) -> None:
        """Save nothing: OPDS params are request-local."""
        del params, defer_last_route

    def user_lists(self) -> tuple[tuple[int, str], ...]:
        """
        Return ``(pk, name)`` for each non-empty reading list of the user's own.

        Ordered by name. Empty for anonymous sessions, who own no lists.
        The v1 and v2 start pages both build their list entries from this.
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return ()
        return tuple(
            ReadingList.objects.filter(
                user=user, entries__comic__isnull=False, entries__ignored=False
            )
            .distinct()
            .order_by("name", "pk")
            .values_list("pk", "name")
        )
