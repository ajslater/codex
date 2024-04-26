"""Constants for models."""

ARTICLES = frozenset(
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
