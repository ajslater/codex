"""Browser Settings and URL Validation."""

from copy import deepcopy
from types import MappingProxyType

from rest_framework.exceptions import NotFound

from codex.choices import DEFAULT_BROWSER_ROUTE, mapping_to_dict
from codex.exceptions import SeeOtherRedirectError
from codex.logger.logging import get_logger
from codex.models.groups import BrowserGroupModel
from codex.views.browser.filters.search.parse import SearchFilterView
from codex.views.const import (
    COMIC_GROUP,
    FOLDER_GROUP,
    GROUP_MODEL_MAP,
    ROOT_GROUP,
    STORY_ARC_GROUP,
)

LOG = get_logger(__name__)


class BrowserValidateView(SearchFilterView):
    """Browser Settings and URL Validation."""

    DEFAULT_ROUTE = MappingProxyType(
        {"name": "browser", "params": DEFAULT_BROWSER_ROUTE}
    )

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._is_admin: bool | None = None
        self._model_group: str = ""
        self._model: type[BrowserGroupModel] | None = None
        self._rel_prefix: str | None = None
        self._valid_nav_groups: tuple[str, ...] | None = None

    @property
    def model_group(self):
        """Memoize the model group."""
        if not self._model_group:
            group = self.kwargs["group"]
            if group == ROOT_GROUP:
                group = self.params["top_group"]
            self._model_group = group
        return self._model_group

    @property
    def model(self) -> type[BrowserGroupModel] | None:
        """Memoize the model for the browse list."""
        if not self._model:
            model = GROUP_MODEL_MAP.get(self.model_group)
            if model is None:
                group = self.kwargs["group"]
                detail = f"Cannot browse {group=}"
                LOG.debug(detail)
                raise NotFound(detail=detail)
            self._model = model
        return self._model

    @property
    def rel_prefix(self):
        """Memoize model rel prefix."""
        if self._rel_prefix is None:
            self._rel_prefix = self.get_rel_prefix(self.model)
        return self._rel_prefix

    def raise_redirect(self, reason, route_mask=None, settings_mask=None):
        """Redirect the client to a valid group url."""
        route = mapping_to_dict(self.DEFAULT_ROUTE)
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

    def _get_valid_browse_nav_groups(self, valid_top_groups):
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

        return tuple(valid_nav_groups)

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
        return valid_top_groups

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
        return self._get_valid_browse_nav_groups(valid_top_groups)

    def _validate_story_arc_settings(self) -> tuple[str, ...]:
        """Validate story arc settings."""
        valid_top_groups = (STORY_ARC_GROUP,)
        self._validate_top_group(valid_top_groups)
        return valid_top_groups

    @property
    def valid_nav_groups(self) -> tuple[str, ...]:
        """Memoize valid nav groups."""
        if self._valid_nav_groups is None:
            group = self.kwargs["group"]
            if group == FOLDER_GROUP:
                vng = self._validate_folder_settings()
            elif group == STORY_ARC_GROUP:
                vng = self._validate_story_arc_settings()
            else:
                vng = self._validate_browser_group_settings()
            self._valid_nav_groups = vng
        return self._valid_nav_groups
