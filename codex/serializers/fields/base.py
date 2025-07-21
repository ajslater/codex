"""Base Fields."""

from abc import ABC
from collections.abc import Sequence

from rest_framework.fields import ChoiceField


class CodexChoiceField(ChoiceField, ABC):
    """Valid class choices."""

    class_choices: Sequence[str] = ()

    def __init__(self, *args, **kwargs):
        """Initialize with choices."""
        super().__init__(*args, choices=self.class_choices, **kwargs)
