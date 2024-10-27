"""Reader Fields."""

from rest_framework.serializers import ChoiceField

from codex.models import Bookmark
from codex.models.comic import ReadingDirection


class FitToField(ChoiceField):
    """Bookmark FitTo Fieild."""

    def __init__(self, *args, **kwargs):
        """Add Choices."""
        super().__init__(*args, choices=Bookmark.FitTo.values, **kwargs)


class ReadingDirectionField(ChoiceField):
    """Reading Direction Field."""

    def __init__(self, *args, **kwargs):
        """Add Choices."""
        super().__init__(*args, choices=ReadingDirection.values, **kwargs)
