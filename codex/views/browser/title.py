"""Browser title."""

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
        group_count = 0
        if gi := self.group_instance:
            if isinstance(gi, Volume):
                group_count = gi.series.volume_count
            elif isinstance(gi, Comic):
                group_count = gi.volume.issue_count
            group_name = gi.name
        else:
            group_name = ""
        return group_name, group_count

    def get_browser_page_title(self):
        """Get the proper title for this browse level."""
        pks = self.kwargs.get("pks")
        if not pks:
            group_name, group_count = self._get_root_group_name()
        else:
            group_name, group_count = self._get_group_name()

        return {
            "group_name": group_name,
            "group_count": group_count,
        }
