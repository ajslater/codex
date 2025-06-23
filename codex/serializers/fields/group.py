"""Browse Group Field."""

from codex.choices.browser import BROWSER_TOP_GROUP_CHOICES
from codex.serializers.fields.base import CodexChoiceField


class BrowseGroupField(CodexChoiceField):
    """Valid Top Groups Only."""

    class_choices = tuple(BROWSER_TOP_GROUP_CHOICES.keys())
