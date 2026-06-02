"""Browser title."""

from collections.abc import Mapping

from codex.models import Comic, Volume
from codex.views.browser.breadcrumbs import BrowserBreadcrumbsView


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

    def _get_collection_name(self) -> tuple:
        collection_number_to = None
        collection_count = 0
        collection_name = ""
        if gi := self.group_instance:
            collection_name = gi.name
            if isinstance(gi, Volume):
                collection_number_to = gi.number_to
                collection_count = gi.series.volume_count
            elif isinstance(gi, Comic):
                collection_number_to = gi.volume.number_to
                collection_count = gi.volume.issue_count
        return collection_name, collection_number_to, collection_count

    def get_browser_page_title(self) -> Mapping:
        """Get the proper title for this browse level."""
        pks = self.kwargs.get("pks")
        if not pks:
            collection_name, collection_count = self._get_root_collection_name()
            collection_number_to = None
        else:
            collection_name, collection_number_to, collection_count = (
                self._get_collection_name()
            )

        return {
            "collection_name": collection_name,
            "collection_number_to": collection_number_to,
            "collection_count": collection_count,
        }
