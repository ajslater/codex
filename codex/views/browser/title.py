"""Browser title."""

from collections.abc import Mapping

from codex.models import Comic, Volume
from codex.views.browser.breadcrumbs import BrowserBreadcrumbsView


class BrowserTitleView(BrowserBreadcrumbsView):
    """Browser title methods."""

    def _get_root_group_name(self):
        if not self.model:
            reason = "No model set in browser"
            raise ValueError(reason)
        plural = self.model._meta.verbose_name_plural
        if not plural:
            reason = f"No plural name for {self.model}"
            raise ValueError(reason)
        return plural.capitalize(), 0

    def _get_group_name(self):
        group_number_to = None
        group_count = 0
        group_name = ""
        if gi := self.group_instance:
            group_name = gi.name
            if isinstance(gi, Volume):
                group_number_to = gi.number_to
                group_count = gi.series.volume_count
            elif isinstance(gi, Comic):
                group_number_to = gi.volume.number_to
                group_count = gi.volume.issue_count
        return group_name, group_number_to, group_count

    def get_browser_page_title(self) -> Mapping:
        """Get the proper title for this browse level."""
        pks = self.kwargs.get("pks")
        if not pks:
            group_name, group_count = self._get_root_group_name()
            group_number_to = None
        else:
            group_name, group_number_to, group_count = self._get_group_name()

        return {
            "group_name": group_name,
            "group_number_to": group_number_to,
            "group_count": group_count,
        }
