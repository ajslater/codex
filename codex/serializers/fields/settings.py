"""Session Custom Fields."""

from codex.choices.browser import BROWSER_DEFAULTS
from codex.choices.reader import READER_DEFAULTS
from codex.serializers.fields.base import CodexChoiceField


class SettingsKeyField(CodexChoiceField):
    """Seettings Field."""

    class_choices = (*READER_DEFAULTS.keys(), *BROWSER_DEFAULTS.keys())
