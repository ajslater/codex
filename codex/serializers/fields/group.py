"""Browse Group Field."""

from codex.choices.browser import BROWSER_ROUTE_CHOICES, BROWSER_TOP_GROUP_CHOICES
from codex.group import group_char, group_value
from codex.serializers.fields.base import CodexChoiceField


class _GroupCharCompatField(CodexChoiceField):
    """
    A group choice field that is char on the wire, collection internally.

    The backend now stores/serves the collection value (``"publishers"``)
    while the frontend still speaks the char dialect (``"p"``). This field
    is the translation edge: it validates + accepts the char wire value and
    hands the engine the collection value, and renders the engine's
    collection value back as the char the frontend expects.
    """

    def to_internal_value(self, data) -> str:
        """Translate the char wire value to the internal collection value."""
        return group_value(super().to_internal_value(data))

    def to_representation(self, value) -> str:
        """Render the internal collection value as the char wire value."""
        return super().to_representation(group_char(value))


class BrowseGroupField(_GroupCharCompatField):
    """Valid Top Groups Only."""

    class_choices = tuple(BROWSER_TOP_GROUP_CHOICES.keys())


class BrowserRouteGroupField(_GroupCharCompatField):
    """Valid Top Groups Only (+ root)."""

    class_choices = tuple(BROWSER_ROUTE_CHOICES.keys())
