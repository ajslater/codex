"""Consts."""

from types import MappingProxyType

CREDIT_PERSON_UI_FIELD = "credits"
STORY_ARC_UI_FIELD = "story_arcs"
IDENTIFIER_TYPE_UI_FIELD = "identifier_source"
BROWSER_FILTER_ARGS = MappingProxyType({"name": ""})
BROWSER_CREATE_ARGS = MappingProxyType({"name": ""})
SHOW_KEYS = frozenset({"p", "i", "s", "v"})
