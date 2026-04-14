"""Common mixin for OPDS Start Page Views."""

from collections.abc import MutableMapping
from typing import Any

from codex.views.opds.const import DEFAULT_PARAMS


class OPDSStartViewMixin:
    """Common mixin for OPDS Start Page Views."""

    IS_START_PAGE = True

    def init_params(self) -> MutableMapping[str, Any]:
        """Hard reset settings to default just by landing on the page."""
        return dict(DEFAULT_PARAMS)

    def _get_group_queryset(self) -> tuple:
        """Force empty group query on start page."""
        qs = self.model.objects.none().order_by("pk")  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        count = 0
        return qs, count
