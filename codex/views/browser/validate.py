"""Browser Settings and URL Validation."""

from copy import deepcopy
from types import MappingProxyType

from codex.exceptions import SeeOtherRedirectError
from codex.logger.logging import get_logger
from codex.serializers.choices import DEFAULTS
from codex.views.browser.base import BrowserBaseView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    ROOT_GROUP,
    STORY_ARC_GROUP,
)

LOG = get_logger(__name__)


class BrowserValidateView(BrowserBaseView):
    """Browser Settings and URL Validation."""

    DEFAULT_ROUTE = MappingProxyType(
        {
            "name": "browser",
            "params": deepcopy(DEFAULTS["breadcrumbs"][0]),
        }
    )

    def raise_redirect(self, reason, route_mask=None, settings_mask=None):
        """Redirect the client to a valid group url."""
        route = deepcopy(dict(self.DEFAULT_ROUTE))
        if route_mask:
            route["params"].update(route_mask)  # type: ignore
        settings = deepcopy(dict(self.params))
        if settings_mask:
            settings.update(settings_mask)
        detail = {"route": route, "settings": settings, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def _get_valid_browse_top_groups(self):
        """Get valid top groups for the current settings.

        Valid top groups are determined by the Browser Settings.
        """
        valid_top_groups = []

        show = self.params["show"]
        for nav_group, allowed in show.items():
            if allowed:
                valid_top_groups.append(nav_group)
        # Issues is always a valid top group
        valid_top_groups += [COMIC_GROUP]

        return valid_top_groups

    def _validate_top_group(self, valid_top_groups):
        nav_group = self.kwargs.get("group")
        top_group = self.params.get("top_group")
        if top_group not in valid_top_groups:
            reason = f"top_group {top_group} not in valid nav groups, changed to "
            if nav_group in valid_top_groups:
                valid_top_group = nav_group
                reason += "nav group: "
            else:
                valid_top_group = valid_top_groups[0]
                reason += "first valid top group "
            reason += valid_top_group
            pks = self.kwargs.get("pks", ())
            page = self.kwargs["page"]
            route = {"group": nav_group, "pks": pks, "page": page}
            breadcrumbs = []
            settings_mask = {"top_group": valid_top_group, "breadcrumbs": breadcrumbs}
            self.raise_redirect(reason, route, settings_mask)

    def set_valid_browse_nav_groups(self, valid_top_groups):
        """Get valid nav groups for the current settings.

        Valid nav groups are the top group and below that are also
        enabled in browser settings.

        May always navigate to root 'r' nav group.
        """
        top_group = self.params["top_group"]
        nav_group = self.kwargs["group"]
        valid_nav_groups = [ROOT_GROUP]

        for possible_index, possible_nav_group in enumerate(valid_top_groups):
            if top_group == possible_nav_group:
                # all the nav groups past this point,
                # 'c' is obscured by the web reader url, but valid for opds
                tail_top_groups = valid_top_groups[possible_index:]
                valid_nav_groups += tail_top_groups
                break
        if nav_group not in valid_nav_groups:
            reason = f"Nav group {nav_group} unavailable, redirect to {ROOT_GROUP}"
            self.raise_redirect(reason)

        self.valid_nav_groups = tuple(valid_nav_groups)

    def _validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        if not self.admin_flags["folder_view"]:
            reason = "folder view disabled"
            valid_top_groups = self._get_valid_browse_top_groups()
            breadcrumbs = []
            settings_mask = {
                "top_group": valid_top_groups[0],
                "breadcrumbs": breadcrumbs,
            }
            self.raise_redirect(reason, settings_mask=settings_mask)

        valid_top_groups = (FOLDER_GROUP,)
        self._validate_top_group(valid_top_groups)
        self.valid_nav_groups = valid_top_groups

    def _validate_browser_group_settings(self):
        """Check that all the view variables for browser mode are set right."""
        # Validate Browser top_group
        # Change top_group if its not in the valid top groups
        valid_top_groups = self._get_valid_browse_top_groups()
        self._validate_top_group(valid_top_groups)

        # Validate pks
        nav_group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        if nav_group == ROOT_GROUP and (pks and 0 not in pks):
            # r never has pks
            reason = f"Redirect r with {pks=} to pks 0"
            self.raise_redirect(reason)

        # Validate Browser nav_group
        # Redirect if nav group is wrong
        self.set_valid_browse_nav_groups(valid_top_groups)

    def _validate_story_arc_settings(self):
        """Validate story arc settings."""
        valid_top_groups = (STORY_ARC_GROUP,)
        self._validate_top_group(valid_top_groups)
        self.valid_nav_groups = valid_top_groups

    def validate_settings(self):
        """Validate group and top group settings."""
        group = self.kwargs["group"]
        if group == FOLDER_GROUP:
            self._validate_folder_settings()
        elif group == STORY_ARC_GROUP:
            self._validate_story_arc_settings()
        else:
            self._validate_browser_group_settings()

        # Validate order
        if self.order_key == "filename" and not self.admin_flags["folder_view"]:
            pks = self.kwargs["pks"]
            page = self.kwargs["page"]
            route_changes = {"group": group, "pks": pks, "page": page}
            reason = "order by filename not allowed by admin flag."
            settings_mask = {"order_by": "sort_name"}
            self.raise_redirect(reason, route_changes, settings_mask)
