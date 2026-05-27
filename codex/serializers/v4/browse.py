"""
v4 browser page serializer.

The v3 ``BrowserPageSerializer`` always emits both the card-mode
fields (``groups`` + ``books``) and the table-mode fields
(``rows``) — the dual emission powered v3's mobile-auto-fallback
that switched to cards on narrow viewports even when the user had
table view enabled. v4 drops that ("pick card or table based on
the request, not both at once" — ``tasks/api-v4.md`` Phase 3): the
serializer reads the active view mode and strips the opposite
shape from the response so the wire stays small and the contract
matches the request.

The mobile-auto-fallback path now refetches with ``?view_mode=card``
when it needs the card shape. The cost is one extra request on
viewport-transition; the benefit is half the wire for every page
load that doesn't transition.
"""

from typing import override

from codex.serializers.browser.page import BrowserPageSerializer


class V4BrowserPageSerializer(BrowserPageSerializer):
    """v4 browser page: mode-aware projection of the v3 shape."""

    @override
    def to_representation(self, instance):
        """Strip the unused mode's fields after the v3 projection."""
        data = super().to_representation(instance)
        view_mode = self._view_mode(instance)
        if view_mode == "table":
            # Table mode: ``rows`` carries every projected column; the
            # card fields are noise (and the largest part of the
            # payload for big pages).
            data.pop("groups", None)
            data.pop("books", None)
        else:
            # Card mode: ``rows`` is empty unless columns were
            # requested, but keep ``groups`` / ``books`` and drop the
            # always-empty ``rows`` slot.
            data.pop("rows", None)
        return data

    @staticmethod
    def _view_mode(instance) -> str:
        """
        Resolve the active view mode from the response payload.

        ``BrowserView`` writes the active ``view_mode`` onto the
        params it serializes; the page dict carries it through.
        Default to ``"cover"`` (card mode) when the value is absent —
        matches the v3 user-facing default.
        """
        if not isinstance(instance, dict):
            return "cover"
        # The instance dict carries ``columns`` only when the request
        # asked for table-mode (BrowserView populates ``columns`` from
        # the user settings only when ``view_mode == "table"``). That
        # gives us a reliable, response-payload-local signal without
        # threading view_mode through every intermediate.
        columns = instance.get("columns")
        return "table" if columns else "cover"
