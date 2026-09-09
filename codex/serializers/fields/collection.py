"""Browse Collection Field."""

from codex.choices.browser import (
    BROWSER_ROUTE_COLLECTION_CHOICES,
    BROWSER_TOP_COLLECTION_CHOICES,
)
from codex.collection import READER_REPRINT_COLLECTION
from codex.serializers.fields.base import CodexChoiceField


class BrowseCollectionField(CodexChoiceField):
    """Valid Top Collections Only (collection vocabulary)."""

    class_choices = tuple(BROWSER_TOP_COLLECTION_CHOICES.keys())


class BrowserRouteCollectionField(CodexChoiceField):
    """Valid Top Collections Only (+ root) — collection vocabulary."""

    class_choices = tuple(BROWSER_ROUTE_COLLECTION_CHOICES.keys())


class MtimeCollectionField(BrowserRouteCollectionField):
    """
    Browse routes plus the reader's alternate-series pseudo-collection.

    The reader probes the mtime of every arc it offers, and one of those
    is a reprint series, which has no browse route of its own. Kept
    separate from :class:`BrowserRouteCollectionField` so a reader-only
    value can't leak into an actual browse route.
    """

    class_choices = (
        *BROWSER_ROUTE_COLLECTION_CHOICES.keys(),
        READER_REPRINT_COLLECTION,
    )
