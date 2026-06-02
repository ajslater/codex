"""Browse Group Field."""

from codex.choices.browser import (
    BROWSER_ROUTE_COLLECTION_CHOICES,
    BROWSER_TOP_COLLECTION_CHOICES,
)
from codex.serializers.fields.base import CodexChoiceField


class BrowseCollectionField(CodexChoiceField):
    """Valid Top Collections Only (collection vocabulary)."""

    class_choices = tuple(BROWSER_TOP_COLLECTION_CHOICES.keys())


class BrowserRouteCollectionField(CodexChoiceField):
    """Valid Top Collections Only (+ root) — collection vocabulary."""

    class_choices = tuple(BROWSER_ROUTE_COLLECTION_CHOICES.keys())
