"""Base model."""

from django.db.models import DateTimeField, Model
from django.db.models.base import ModelBase
from typing_extensions import override

from codex.models.fields import CleaningCharField
from codex.models.query import GroupByManager

__all__ = ("BaseModel", "NamedModel")

MAX_PATH_LEN = 4095
MAX_NAME_LEN = 128
MAX_FIELD_LEN = 32
MAX_ISSUE_SUFFIX_LEN = 16


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    objects = GroupByManager()

    class Meta(ModelBase):
        """Without this a real table is created and joined to."""

        # Model.Meta is not inheritable.

        abstract = True
        get_latest_by = "updated_at"

    def presave(self):
        """Create values before save."""


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CleaningCharField(db_index=True, max_length=MAX_NAME_LEN)

    class Meta(BaseModel.Meta):
        """Defaults to uniquely named, must be overridden."""

        abstract = True
        unique_together: tuple[str, ...] = ("name",)

    @override
    def __repr__(self):
        """Return the name."""
        return self.name
