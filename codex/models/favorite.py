"""Favorite model."""

from typing import Final

from django.conf import settings
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    PositiveIntegerField,
)

from codex.models.base import BaseModel

__all__ = ("FAVORITE_GROUP_CHOICES", "Favorite")

FAVORITE_GROUP_CHOICES: Final = (
    ("p", "Publisher"),
    ("i", "Imprint"),
    ("s", "Series"),
    ("v", "Volume"),
    ("f", "Folder"),
    ("a", "Story Arc"),
    ("c", "Comic"),
)


class Favorite(BaseModel):
    """Per-user favorite tag for a browseable group or comic."""

    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    group = CharField(max_length=1, choices=FAVORITE_GROUP_CHOICES)
    target_id = PositiveIntegerField()

    class Meta(BaseModel.Meta):
        """Uniqueness across (user, group, target_id)."""

        unique_together = ("user", "group", "target_id")
