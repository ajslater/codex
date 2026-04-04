"""Settings View Consts."""

from types import MappingProxyType

CREDIT_PERSON_UI_FIELD = "credits"
STORY_ARC_UI_FIELD = "story_arcs"
IDENTIFIER_TYPE_UI_FIELD = "identifier_source"
SETTINGS_BROWSER_SELECT_RELATED = ("show", "filters", "last_route")

BROWSER_FILTER_ARGS = MappingProxyType({"name": ""})
BROWSER_CREATE_ARGS = MappingProxyType({"name": ""})
SHOW_KEYS = frozenset({"p", "i", "s", "v"})
