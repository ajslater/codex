"""Favorite model."""

from types import MappingProxyType
from typing import Final

from django.conf import settings
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    PositiveIntegerField,
)

from codex.models.base import BaseModel
from codex.models.comic import Comic
from codex.models.groups import Folder, Imprint, Publisher, Series, Volume
from codex.models.named import StoryArc

__all__ = (
    "FAVORITE_GROUP_CHOICES",
    "FAVORITE_GROUP_CODE_MODELS",
    "FAVORITE_MODEL_GROUP_CODES",
    "Favorite",
)

FAVORITE_GROUP_CHOICES: Final = (
    ("p", "Publisher"),
    ("i", "Imprint"),
    ("s", "Series"),
    ("v", "Volume"),
    ("f", "Folder"),
    ("a", "Story Arc"),
    ("c", "Comic"),
)

# Single source of truth for the model ↔ group-letter dispatch.
# Every favorite-related view, signal, cron, and annotation pulls
# from these maps so the seven group letters stay aligned across
# the codebase. Filter / annotation / API views consume the
# forward map; the cleanup cron and signal handler consume the
# reverse map. Both are immutable proxies.
FAVORITE_MODEL_GROUP_CODES: Final[MappingProxyType[type, str]] = MappingProxyType(
    {
        Publisher: "p",
        Imprint: "i",
        Series: "s",
        Volume: "v",
        Folder: "f",
        StoryArc: "a",
        Comic: "c",
    }
)
FAVORITE_GROUP_CODE_MODELS: Final[MappingProxyType[str, type]] = MappingProxyType(
    {code: model for model, code in FAVORITE_MODEL_GROUP_CODES.items()}
)


class Favorite(BaseModel):
    """Per-user favorite tag for a browseable group or comic."""

    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    group = CharField(max_length=1, choices=FAVORITE_GROUP_CHOICES)
    target_id = PositiveIntegerField()

    class Meta(BaseModel.Meta):
        """Uniqueness across (user, group, target_id)."""

        unique_together = ("user", "group", "target_id")
