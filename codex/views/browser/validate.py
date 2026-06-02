"""Browser Settings and URL Validation."""

from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, NoReturn, cast

from loguru import logger
from rest_framework.exceptions import NotFound

from codex.choices.browser import DEFAULT_BROWSER_ROUTE
from codex.models.collections import BrowserCollectionModel
from codex.util import mapping_to_dict
from codex.views.browser.filters.search.parse import SearchFilterView
from codex.views.const import (
    COLLECTION_MODEL_MAP,
    COMIC_COLLECTION,
    FOLDER_COLLECTION,
    ROOT_COLLECTION,
    STORY_ARC_COLLECTION,
)
from codex.views.exceptions import SeeOtherRedirectError


class BrowserValidateView(SearchFilterView):
    """Browser Settings and URL Validation."""

    DEFAULT_ROUTE = MappingProxyType(
        {"name": "browser", "params": DEFAULT_BROWSER_ROUTE}
    )

    def __init__(self, *args, **kwargs) -> None:
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._is_admin: bool | None = None
        self._model_collection: str = ""
        self._model: type[BrowserCollectionModel] | None = None
        self._rel_prefix: str | None = None
        self._valid_nav_collections: tuple[str, ...] | None = None

    @property
    def model_collection(self) -> str:
        """Memoize the model group."""
        if not self._model_collection:
            group = self.kwargs["collection"]
            if group == ROOT_COLLECTION:
                group = self.params["top_collection"]
            self._model_collection = group
        return self._model_collection

    @property
    def model(self) -> type[BrowserCollectionModel] | None:
        """Memoize the model for the browse list."""
        if not self._model:
            model = COLLECTION_MODEL_MAP.get(self.model_collection)
            if model is None:
                group = self.kwargs["collection"]
                detail = f"Cannot browse {group=}"
                logger.debug(detail)
                raise NotFound(detail=detail)
            self._model = model
        return self._model

    @property
    def rel_prefix(self) -> str:
        """Memoize model rel prefix."""
        if self._rel_prefix is None:
            self._rel_prefix = self.get_rel_prefix(self.model)
        return self._rel_prefix

    def raise_redirect(
        self, reason, route_mask=None, settings_mask: Mapping | None = None
    ) -> NoReturn:
        """Redirect the client to a valid group url."""
        route = cast("dict[str, Any]", mapping_to_dict(self.DEFAULT_ROUTE))
        if route_mask:
            route["params"].update(route_mask)
        settings = cast("dict[str, Any]", deepcopy(mapping_to_dict(self.params)))
        if settings_mask:
            settings.update(settings_mask)
        detail = {"route": route, "settings": settings, "reason": reason}
        raise SeeOtherRedirectError(detail=detail)

    def _get_valid_browse_top_collections(self) -> list:
        """
        Get valid top groups for the current settings.

        Valid top groups are determined by the Browser Settings.
        """
        show = self.params["show"]
        # Issues is always a valid top group; appended after the
        # show-driven groups so the existing ordering is preserved.
        return [
            *(nav_collection for nav_collection, allowed in show.items() if allowed),
            COMIC_COLLECTION,
        ]

    def _validate_top_group(self, valid_top_collections) -> None:
        nav_collection = self.kwargs.get("collection")
        top_collection = self.params.get("top_collection")
        if top_collection not in valid_top_collections:
            reason = f"top_collection {top_collection} not in valid nav groups {valid_top_collections}, changed to "
            if nav_collection in valid_top_collections:
                valid_top_group = nav_collection
                reason += "nav group: "
            else:
                valid_top_group = valid_top_collections[0]
                reason += "first valid top group "
            reason += valid_top_group
            pks = self.kwargs.get("pks", ())
            page = self.kwargs["page"]
            route = {"collection": nav_collection, "pks": pks, "page": page}
            settings_mask = {"top_collection": valid_top_group}
            self.raise_redirect(reason, route, settings_mask)

    def _get_valid_browse_nav_collections(self, valid_top_collections) -> tuple:
        """
        Get valid nav groups for the current settings.

        Valid nav groups are the top group and below that are also
        enabled in browser settings.

        May always navigate to root 'r' nav group.
        """
        top_collection = self.params["top_collection"]
        nav_collection = self.kwargs["collection"]
        valid_nav_collections = [ROOT_COLLECTION]

        for possible_index, possible_nav_collection in enumerate(valid_top_collections):
            if top_collection == possible_nav_collection:
                # all the nav groups past this point,
                # 'c' is obscured by the web reader url, but valid for opds
                tail_top_collections = valid_top_collections[possible_index:]
                valid_nav_collections += tail_top_collections
                break
        if nav_collection not in valid_nav_collections:
            reason = (
                f"Nav group {nav_collection} unavailable, redirect to {ROOT_COLLECTION}"
            )
            self.raise_redirect(reason)

        return tuple(valid_nav_collections)

    def _validate_folder_settings(self) -> tuple:
        """Check that all the view variables for folder mode are set right."""
        # Check folder view admin flag
        if not self.admin_flags["folder_view"]:
            reason = "folder view disabled"
            valid_top_collections = self._get_valid_browse_top_collections()
            settings_mask = {"top_collection": valid_top_collections[0]}
            self.raise_redirect(reason, settings_mask=settings_mask)

        valid_top_collections = (FOLDER_COLLECTION,)
        self._validate_top_group(valid_top_collections)
        return valid_top_collections

    def _validate_browser_collection_settings(self) -> tuple:
        """Check that all the view variables for browser mode are set right."""
        # Validate Browser top_collection
        # Change top_collection if its not in the valid top groups
        valid_top_collections = self._get_valid_browse_top_collections()
        self._validate_top_group(valid_top_collections)

        # Validate pks
        nav_collection = self.kwargs["collection"]
        pks = self.kwargs["pks"]
        if nav_collection == ROOT_COLLECTION and (pks and 0 not in pks):
            # r never has pks
            reason = f"Redirect r with {pks=} to pks 0"
            self.raise_redirect(reason)

        # Validate Browser nav_collection
        # Redirect if nav group is wrong
        return self._get_valid_browse_nav_collections(valid_top_collections)

    def _validate_story_arc_settings(self) -> tuple[str, ...]:
        """Validate story arc settings."""
        valid_top_collections = (STORY_ARC_COLLECTION,)
        self._validate_top_group(valid_top_collections)
        return valid_top_collections

    @property
    def valid_nav_collections(self) -> tuple[str, ...]:
        """Memoize valid nav groups."""
        if self._valid_nav_collections is None:
            group = self.kwargs["collection"]
            validate_group = (
                self.params["top_collection"] if group == COMIC_COLLECTION else group
            )

            if validate_group == FOLDER_COLLECTION:
                vng = self._validate_folder_settings()
            elif validate_group == STORY_ARC_COLLECTION:
                vng = self._validate_story_arc_settings()
            else:
                vng = self._validate_browser_collection_settings()
            self._valid_nav_collections = vng
        return self._valid_nav_collections
