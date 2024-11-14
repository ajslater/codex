"""Browser Group Field."""

from rest_framework.fields import ChoiceField

from codex.choices.browser import BROWSER_GROUP_CHOICES


class BrowseGroupField(ChoiceField):
    """BrowseGroup Field."""

    def __init__(self, *args, **kwargs):
        """Add choices."""
        super().__init__(*args, choices=tuple(BROWSER_GROUP_CHOICES.keys()), **kwargs)
