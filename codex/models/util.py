"""Utilities for models."""

_ARTICLES = frozenset(
    ("a", "an", "the")  # en    # noqa RUF005
    + ("un", "unos", "unas", "el", "los", "la", "las")  # es
    + ("un", "une", "le", "les", "la", "les", "l'")  # fr
    + ("o", "a", "os")  # pt
    # pt "as" conflicts with English
    + ("der", "dem", "des", "das")  # de
    # de: "den & die conflict with English
    + ("il", "lo", "gli", "la", "le", "l'")  # it
    # it: "i" conflicts with English
    + ("de", "het", "een")  # nl
    + ("en", "ett")  # sw
    + ("en", "ei", "et")  # no
    + ("en", "et")  # da
    + ("el", "la", "els", "les", "un", "una", "uns", "unes", "na")  # ct
)


def get_sort_name(name: str) -> str:
    """Create sort_name from name."""
    lower_name = name.lower()
    sort_name = lower_name
    name_parts = lower_name.split()
    if len(name_parts) > 1:
        first_word = name_parts[0]
        if first_word in _ARTICLES:
            sort_name = " ".join(name_parts[1:])
            sort_name += ", " + first_word
    return sort_name
