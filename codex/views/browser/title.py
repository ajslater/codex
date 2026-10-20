"""Browser title."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from codex.models import Comic, Series, Volume
from codex.views.browser.breadcrumbs import BrowserBreadcrumbsView

_EMPTY_TITLE: Final = MappingProxyType(
    {
        "collection_name": "",
        "collection_number_to": None,
        "collection_count": 0,
        "collection_start_year": None,
        "collection_end_year": None,
    }
)


class BrowserTitleView(BrowserBreadcrumbsView):
    """Browser title methods."""

    def _get_root_collection_name(self) -> tuple:
        if not self.model:
            reason = "No model set in browser"
            raise ValueError(reason)
        plural = self.model._meta.verbose_name_plural
        if not plural:
            reason = f"No plural name for {self.model}"
            raise ValueError(reason)
        return plural.capitalize(), 0

    def _get_collection_name(self) -> Mapping:
        """
        Name the collection the route points at.

        The second consumer of ``collection_instance``, and the one both
        OPDS versions reach through ``get_browser_page_title``. Reading
        the property is what raises the 303 when the route names a
        collection this user cannot see, so the empty defaults below are
        now only the root-listing case (no pks).
        """
        title = dict(_EMPTY_TITLE)
        if gi := self.collection_instance:
            title["collection_name"] = gi.name
            if isinstance(gi, Series):
                title["collection_start_year"] = gi.start_year
                title["collection_end_year"] = gi.end_year
            elif isinstance(gi, Volume):
                title["collection_number_to"] = gi.number_to
                title["collection_count"] = gi.series.volume_count
            elif isinstance(gi, Comic):
                title["collection_number_to"] = gi.volume.number_to
                title["collection_count"] = gi.volume.issue_count
        return title

    def get_browser_page_title(self) -> Mapping:
        """Get the proper title for this browse level."""
        if self.kwargs.get("pks"):
            return self._get_collection_name()
        collection_name, collection_count = self._get_root_collection_name()
        return {
            **_EMPTY_TITLE,
            "collection_name": collection_name,
            "collection_count": collection_count,
        }
