"""Base model."""

from django.db.models import DateTimeField, Model
from django.db.models.base import ModelBase

__all__ = ("BaseModel",)

MAX_NAME_LEN = 128
MAX_FIELD_LEN = 32


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta(ModelBase):  # type: ignore
        """Without this a real table is created and joined to."""

        abstract = True
        get_latest_by = "updated_at"
