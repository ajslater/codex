"""Session Custom Fields."""

from rest_framework.fields import ChoiceField

from codex.choices.browser import BROWSER_DEFAULTS
from codex.choices.reader import READER_DEFAULTS

_SESSION_KEYS = (*READER_DEFAULTS.keys(), *BROWSER_DEFAULTS.keys(), "filters")


class SessionKeyField(ChoiceField):
    """Session Key Field."""

    def __init__(self, *args, **kwargs):
        """Add choices."""
        super().__init__(*args, choices=_SESSION_KEYS, **kwargs)
