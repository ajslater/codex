"""Utilities for models."""

# Multi-language leading-article set used by ``get_sort_name`` to
# move a leading "the"/"el"/"der"/etc. to the end so titles sort by
# the first significant word. Comments mark which language each
# group came from; cross-language collisions (English "as" vs
# Portuguese "as", English "i" vs Italian "i", etc.) are
# intentionally absent.
_ARTICLES = frozenset(
    {
        # en
        "a", "an", "the",
        # es
        "un", "unos", "unas", "el", "los", "la", "las",
        # fr (l' is shared with it)
        "une", "le", "les", "l'",
        # pt
        "o", "os",
        # de (den & die conflict with English)
        "der", "dem", "des", "das",
        # it (i conflicts with English)
        "il", "lo", "gli",
        # nl
        "de", "het", "een",
        # sw / no / da
        "en", "ett", "ei", "et",
        # ct
        "els", "una", "uns", "unes", "na",
    }
)  # fmt: skip


def get_sort_name(name: str) -> str:
    """Create sort_name from name."""
    lower_name = name.lower()
    name_parts = lower_name.split()
    if len(name_parts) > 1 and (first_word := name_parts[0]) in _ARTICLES:
        return " ".join(name_parts[1:]) + ", " + first_word
    return lower_name
