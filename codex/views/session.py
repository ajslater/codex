"""Manage user sessions with appropriate defaults."""

from abc import ABC
from collections.abc import MutableMapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any

from loguru import logger

from codex.choices.browser import BROWSER_DEFAULTS
from codex.choices.reader import READER_DEFAULTS
from codex.util import mapping_to_dict
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP

CREDIT_PERSON_UI_FIELD = "credits"
STORY_ARC_UI_FIELD = "story_arcs"
IDENTIFIER_TYPE_UI_FIELD = "identifier_source"

_DYNAMIC_FILTER_DEFAULTS = MappingProxyType(
    {
        "age_rating": [],
        "characters": [],
        "country": [],
        CREDIT_PERSON_UI_FIELD: [],
        "critical_rating": [],
        "decade": [],
        "file_type": [],
        "genres": [],
        IDENTIFIER_TYPE_UI_FIELD: [],
        "language": [],
        "locations": [],
        "monochrome": [],
        "original_format": [],
        "reading_direction": [],
        "series_groups": [],
        "stories": [],
        STORY_ARC_UI_FIELD: [],
        "tagger": [],
        "tags": [],
        "teams": [],
        "universes": [],
        "year": [],
    }
)


class SessionView(AuthFilterGenericAPIView, ABC):
    """Generic Session View."""

    # Must override this
    SESSION_KEY: str = ""
    FILTER_ATTRIBUTES: frozenset[str] = frozenset(_DYNAMIC_FILTER_DEFAULTS.keys())
    BROWSER_SESSION_KEY: str = "browser"
    READER_SESSION_KEY: str = "reader"
    SESSION_DEFAULTS = MappingProxyType(
        {
            BROWSER_SESSION_KEY: {
                **BROWSER_DEFAULTS,
                "filters": {
                    "bookmark": BROWSER_DEFAULTS["bookmark_filter"],
                    **_DYNAMIC_FILTER_DEFAULTS,
                },
            },
            READER_SESSION_KEY: READER_DEFAULTS,
        }
    )

    def get_from_session(
        self, key, default=None, session_key=None
    ):  # only used by frontend
        """Get one key from the session or its default."""
        if session_key is None:
            session_key = self.SESSION_KEY
        session = self.request.session.get(
            session_key, self.SESSION_DEFAULTS[session_key]
        )
        if default is None:
            default = self.SESSION_DEFAULTS[session_key][key]
        return session.get(key, default)

    def get_last_route(self):
        """Get the last route from the session."""
        return self.get_from_session("last_route", session_key=self.BROWSER_SESSION_KEY)

    def save_last_route(self, data: MutableMapping):
        """Save last route to data."""
        last_route = {
            "group": self.kwargs.get("group", "r"),
            "pks": self.kwargs.get("pks", (0,)),
            "page": self.kwargs.get("page", 1),
        }
        data["last_route"].update(last_route)

    @classmethod
    def _get_source_values_or_set_defaults(cls, defaults_dict, source_dict, data):
        """Recursively copy source_dict values into data or use defaults."""
        result = deepcopy(data)
        for key, default_value in defaults_dict.items():
            result[key] = source_dict.get(key, default_value)
            if result[key] is None:
                # extra check for migrated or corrupt data
                result[key] = default_value
            if isinstance(default_value, dict):
                result[key] = cls._get_source_values_or_set_defaults(
                    default_value, source_dict.get(key, {}), result[key]
                )
        return result

    def _get_browser_order_defaults(self) -> dict:
        if group := self.kwargs.get("group"):
            # order_by has a dynamic group based default
            order_by = (
                "filename"
                if group == FOLDER_GROUP
                else "story_arc_number"
                if group == STORY_ARC_GROUP
                else "sort_name"
            )
            order_defaults = {"order_by": order_by}
        else:
            order_defaults = {}
        return order_defaults

    def get_param_defaults(self, session_key: str = "", only: list[str] | None = None):
        """Get default params."""
        if not session_key:
            session_key = self.SESSION_KEY
        if only:
            defaults: dict[str, Any] = {}
            for key in only:
                if key:
                    defaults[key] = mapping_to_dict(
                        self.SESSION_DEFAULTS[session_key][key]
                    )
        else:
            defaults = mapping_to_dict(self.SESSION_DEFAULTS[session_key])
        if session_key == self.BROWSER_SESSION_KEY:
            # There's no BrowserSession so conditional on session key.
            order_defaults = self._get_browser_order_defaults()
            defaults.update(order_defaults)
        return defaults

    def load_params_from_session(
        self, session_key: str | None = None, only: list[str] | None = None
    ):
        """Get session settings with defaults."""
        if not session_key:
            session_key = self.SESSION_KEY

        defaults = self.get_param_defaults(session_key, only)
        session = self.request.session.get(session_key, defaults)
        return self._get_source_values_or_set_defaults(defaults, session, {})

    def save_params_to_session(self, params):  # reader session & browser final
        """Save the session from params with defaults for missing values."""
        try:
            # Deepcopy this so serializing the values later later for http response doesn't alter them
            params = deepcopy(dict(params))
            defaults = mapping_to_dict(self.SESSION_DEFAULTS[self.SESSION_KEY])
            data = self._get_source_values_or_set_defaults(defaults, params, {})
            data = mapping_to_dict(data)
            self.request.session[self.SESSION_KEY] = data
            self.request.session.save()
        except Exception as exc:
            logger.warning(f"Saving params to session: {exc}")
