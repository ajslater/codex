"""Manage user sessions with appropriate defaults."""

from abc import ABC
from copy import deepcopy
from types import MappingProxyType

from codex.logger.logging import get_logger
from codex.serializers.choices import DEFAULTS
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.util import pop_name

LOG = get_logger(__name__)


class SessionView(AuthFilterGenericAPIView, ABC):
    """Generic Session View."""

    # Must override both of these
    SESSION_KEY = ""

    CONTRIBUTOR_PERSON_UI_FIELD = "contributors"
    STORY_ARC_UI_FIELD = "story_arcs"
    IDENTIFIER_TYPE_UI_FIELD = "identifier_type"
    _DYNAMIC_FILTER_DEFAULTS = MappingProxyType(
        {
            "age_rating": [],
            "characters": [],
            "country": [],
            CONTRIBUTOR_PERSON_UI_FIELD: [],
            "community_rating": [],
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
            "year": [],
        }
    )
    FILTER_ATTRIBUTES = frozenset(_DYNAMIC_FILTER_DEFAULTS.keys())
    BROWSER_SESSION_KEY = "browser"
    READER_SESSION_KEY = "reader"
    SESSION_DEFAULTS = MappingProxyType(
        {
            BROWSER_SESSION_KEY: {
                "breadcrumbs": DEFAULTS["breadcrumbs"],
                "filters": {
                    "bookmark": DEFAULTS["bookmarkFilter"],
                    **_DYNAMIC_FILTER_DEFAULTS,
                },
                "order_by": DEFAULTS["orderBy"],
                "order_reverse": DEFAULTS["orderReverse"],
                "q": DEFAULTS["q"],
                "search_results_limit": DEFAULTS["searchResultsLimit"],
                "show": DEFAULTS["show"],
                "dynamic_covers": DEFAULTS["dynamicCovers"],
                "custom_covers": DEFAULTS["customCovers"],
                "twenty_four_hour_time": DEFAULTS["twentyFourHourTime"],
                "top_group": DEFAULTS["topGroup"],
            },
            READER_SESSION_KEY: {
                "finish_on_last_page": DEFAULTS["finishOnLastPage"],
                "fit_to": DEFAULTS["fitTo"],
                "two_pages": DEFAULTS["twoPages"],
                "read_rtl_in_reverse": DEFAULTS["readRtlInReverse"],
                "reading_direction": DEFAULTS["readingDirection"],
            },
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

    def get_last_route(self, name=True):
        """Get the last route from the breadcrumbs."""
        breadcrumbs = self.get_from_session(
            "breadcrumbs", session_key=self.BROWSER_SESSION_KEY
        )
        if not breadcrumbs:
            breadcrumbs = DEFAULTS["breadcrumbs"]
        last_route = breadcrumbs[-1]
        if not name:
            last_route = pop_name(last_route)

        return last_route

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

    def load_params_from_session(self, session_key=None, only=None):
        """Get session settings with defaults."""
        if not session_key:
            session_key = self.SESSION_KEY
        if only:
            defaults = {}
            for key in only:
                if key:
                    defaults[key] = self.SESSION_DEFAULTS[session_key][key]
        else:
            defaults = self.SESSION_DEFAULTS[session_key]

        session = self.request.session.get(session_key, defaults)
        return self._get_source_values_or_set_defaults(defaults, session, {})

    def save_params_to_session(self, params):  # reader session & browser final
        """Save the session from params with defaults for missing values."""
        try:
            # Deepcopy this so serializing the values later later for http response doesn't alter them
            params = deepcopy(dict(params))
            defaults = self.SESSION_DEFAULTS[self.SESSION_KEY]
            data = self._get_source_values_or_set_defaults(defaults, params, {})
            self.request.session[self.SESSION_KEY] = data
            self.request.session.save()
        except Exception as exc:
            LOG.warning(f"Saving params to session: {exc}")
