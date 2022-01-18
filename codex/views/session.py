"""Manage user sessions with appropriate defaults."""
from rest_framework.views import APIView

from codex.serializers.choices import DEFAULTS


class SessionView(APIView):
    """Generic Session View."""

    CREDIT_PERSON_UI_FIELD = "creators"
    _DYNAMIC_FILTER_DEFAULTS = {
        "autoquery": "",
        "characters": [],
        "country": [],
        CREDIT_PERSON_UI_FIELD: [],
        "critical_rating": [],
        "decade": [],
        "format": [],
        "genres": [],
        "language": [],
        "locations": [],
        "maturity_rating": [],
        "read_ltr": [],
        "series_groups": [],
        "story_arcs": [],
        "tags": [],
        "teams": [],
        "user_rating": [],
        "year": [],
    }
    FILTER_ATTRIBUTES = set(_DYNAMIC_FILTER_DEFAULTS.keys())
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
        READER_KEY: {"defaults": {"fit_to": DEFAULTS["fitTo"], "two_pages": False}},
    }

    def get_session(self, session_key=None):
        """Create or get the view session."""
        if session_key is None:
            session_key = self.SESSION_KEY
        defaults = self.SESSION_DEFAULTS[session_key]
        data = self.request.session.setdefault(session_key, defaults)
        key_session = self.request.session[session_key]

        # Set defaults for each key in case they don't exist.
        for key, value in defaults.items():
            data[key] = key_session.setdefault(key, value)
            if isinstance(value, dict):
                # Just one level. No need for recursion.
                for deep_key, deep_value in defaults[key].items():
                    data[key][deep_key] = key_session[key].setdefault(
                        deep_key, deep_value
                    )

        return data

    def save_session(self, params):
        """Save the session, with defaults if necessary."""
        data = {}
        for key, value in self.SESSION_DEFAULTS[self.SESSION_KEY].items():
            if isinstance(value, dict):
                # Just one level. No need for recursion.
                data[key] = {}
                for deep_key, deep_value in value.items():
                    data[key][deep_key] = params[key].get(deep_key, deep_value)
            else:
                data[key] = params.get(key, value)

        self.request.session[self.SESSION_KEY] = data
        self.request.session.save()
