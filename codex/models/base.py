"""Base model."""

from django.db.models import DateTimeField, Model
from django.db.models.base import ModelBase

from codex.models.query import GroupByManager

__all__ = ("BaseModel",)

MAX_PATH_LEN = 4095
MAX_NAME_LEN = 128
MAX_FIELD_LEN = 32
MAX_ISSUE_SUFFIX_LEN = 16


def max_choices_len(choices):
    """Return the maximum possible size for a Choice's key."""
    if not isinstance(choices, tuple):
        choices = choices.choices
    return max(len(choice[0]) for choice in choices)


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    objects = GroupByManager()

    class Meta(ModelBase):  # type: ignore
        """Without this a real table is created and joined to."""

        abstract = True
        get_latest_by = "updated_at"

    def presave(self):
        """Create values before save."""
