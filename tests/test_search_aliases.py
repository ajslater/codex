"""
Search field aliases are names, never the letters of one.

``"language": ("lang")`` is a string, not a one-element tuple, so its
aliases were ``l``, ``a``, ``n`` and ``g``: ``lang:`` did not search the
language, and ``a:`` did.
"""

from codex.choices.search import FIELDMAP, SEARCH_FIELDS
from codex.views.browser.filters.search.parse import _ALIAS_FIELD_MAP


def test_every_alias_entry_is_a_tuple() -> None:
    """A bare string would split into one-letter aliases."""
    strings = sorted(key for key, values in FIELDMAP.items() if isinstance(values, str))
    assert not strings, f"aliases written as a string, not a tuple: {strings}"


def test_lang_searches_the_language() -> None:
    """``lang:`` names the language field; its letters name nothing."""
    assert _ALIAS_FIELD_MAP["lang"] == "language"
    assert SEARCH_FIELDS["language"]["aliases"] == ("lang",)
    assert all(_ALIAS_FIELD_MAP.get(letter) != "language" for letter in "lang")
