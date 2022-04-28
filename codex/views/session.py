"""Manage user sessions with appropriate defaults."""
from rest_framework.views import APIView

from codex.serializers.choices import DEFAULTS
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class SessionView(APIView):
    """Generic Session View."""

    CREDIT_PERSON_UI_FIELD = "creators"
    _DYNAMIC_FILTER_DEFAULTS = {
        "age_rating": [],
        "autoquery": "",
        "characters": [],
        "country": [],
        CREDIT_PERSON_UI_FIELD: [],
        "community_rating": [],
        "critical_rating": [],
        "decade": [],
        "format": [],
        "genres": [],
        "language": [],
        "locations": [],
        "read_ltr": [],
        "series_groups": [],
        "story_arcs": [],
        "tags": [],
        "teams": [],
        "year": [],
    }
    FILTER_ATTRIBUTES = frozenset(_DYNAMIC_FILTER_DEFAULTS.keys())
    SESSION_KEY = "UNDEFINED"  # Must override
    BROWSER_KEY = "browser"
    READER_KEY = "reader"
    SESSION_DEFAULTS = {
        BROWSER_KEY: {
            "filters": {
                "bookmark": DEFAULTS["bookmarkFilter"],
                **_DYNAMIC_FILTER_DEFAULTS,
            },
            "autoquery": DEFAULTS["autoquery"],
            "top_group": DEFAULTS["topGroup"],
            "order_by": DEFAULTS["orderBy"],
            "order_reverse": False,
            "show": DEFAULTS["show"],
            "route": DEFAULTS["route"],
        },
        READER_KEY: {"display": {"fit_to": DEFAULTS["fitTo"], "two_pages": False}},
    }

    def _get_defaults_and_session(self, session_key: str):
        """Get the session defaults and the session."""
        defaults = self.SESSION_DEFAULTS[session_key]
        session = self.request.session.get(session_key, defaults)
        return defaults, session

    @classmethod
    def _get_source_values_or_set_defaults(cls, defaults_dict, source_dict, data):
        """Recursively copy source_dict values into data or use defaults."""
        for key, default_value in defaults_dict.items():
            data[key] = source_dict.get(key, default_value)
            if data[key] is None:
                # extra check for migrated or corrupt data
                data[key] = default_value
            if isinstance(default_value, dict):
                cls._get_source_values_or_set_defaults(
                    default_value, source_dict.get(key, {}), data[key]
                )

    def load_params_from_session(self):
        """Set the params from view session, creating missing values from defaults."""
        defaults, session = self._get_defaults_and_session(self.SESSION_KEY)
        data = {}

        self._get_source_values_or_set_defaults(defaults, session, data)
        self.params = data

    def get_from_session(self, key, session_key=None):
        """Get one key from the session or its default."""
        if session_key is None:
            session_key = self.SESSION_KEY
        defaults, session = self._get_defaults_and_session(session_key)
        value = session.get(key, defaults[key])
        return value

    def save_params_to_session(self):
        """Save the session from params with defaults for missing values."""
        try:
            defaults = self.SESSION_DEFAULTS[self.SESSION_KEY]
            data = {}
            self._get_source_values_or_set_defaults(defaults, self.params, data)
            self.request.session[self.SESSION_KEY] = data
            self.request.session.save()
        except Exception as exc:
            LOG.warning(f"Saving params to session: {exc}")
