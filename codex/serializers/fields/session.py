"""Session Custom Fields."""

from rest_framework.fields import ChoiceField

from codex.choices import BROWSER_DEFAULTS, READER_DEFAULTS

_SESSION_KEYS = (*READER_DEFAULTS.keys(), *BROWSER_DEFAULTS.keys(), "filters")


class SessionKeyField(ChoiceField):
    """Session Key Field."""

    def __init__(self, *args, **kwargs):
        """Add choices."""
        super().__init__(*args, choices=_SESSION_KEYS, **kwargs)
