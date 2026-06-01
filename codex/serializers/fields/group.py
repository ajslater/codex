"""Browse Group Field."""

from codex.choices.browser import (
    BROWSER_ROUTE_COLLECTION_CHOICES,
    BROWSER_TOP_GROUP_COLLECTION_CHOICES,
)
from codex.serializers.fields.base import CodexChoiceField


class BrowseGroupField(CodexChoiceField):
    """Valid Top Groups Only (collection vocabulary)."""

    class_choices = tuple(BROWSER_TOP_GROUP_COLLECTION_CHOICES.keys())


class BrowserRouteGroupField(CodexChoiceField):
    """Valid Top Groups Only (+ root) — collection vocabulary."""

    class_choices = tuple(BROWSER_ROUTE_COLLECTION_CHOICES.keys())
