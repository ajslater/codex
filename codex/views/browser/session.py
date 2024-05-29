"""Browser session view."""

from types import MappingProxyType

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.serializers.choices import DEFAULTS
from codex.views.session import SessionViewBase, SessionViewBaseBase


class BrowserSessionViewBase(SessionViewBaseBase):
    """Browser session base."""

    SESSION_KEY = "browser"  # type: ignore
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
    SESSION_DEFAULTS = MappingProxyType(
        {
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
            "cover_style": DEFAULTS["coverStyle"],
            "twenty_four_hour_time": False,
            "top_group": DEFAULTS["topGroup"],
        }
    )

    def get_last_route(self, name=True):
        """Get the last route from the breadcrumbs."""
        breadcrumbs = self.get_from_session("breadcrumbs")
        if not breadcrumbs:
            breadcrumbs = DEFAULTS["breadcrumbs"]
        last_route = breadcrumbs[-1]
        if not name:
            last_route.pop("name", None)

        return last_route


class BrowserSessionView(BrowserSessionViewBase, SessionViewBase):
    """Get Browser Settings."""

    # Put Browser Settings is normally done through BrowserView.get()

    serializer_class = BrowserSettingsSerializer  # type: ignore
