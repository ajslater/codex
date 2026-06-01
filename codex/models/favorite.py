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

from codex.group import GROUP_LABELS, Group
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

# Single source of truth for the model ↔ group dispatch. The group code
# is the collection vocabulary (a :class:`Group` member, whose value is
# the collection name) shared by the whole app. Every favorite-related
# view, signal, cron, and annotation pulls from these maps so the seven
# groups stay aligned across the codebase. Filter / annotation / API
# views consume the forward map; the cleanup cron and signal handler
# consume the reverse map. Both are immutable proxies.
FAVORITE_MODEL_GROUP_CODES: Final[MappingProxyType[type[BaseModel], str]] = (
    MappingProxyType(
        {
            Publisher: Group.PUBLISHER,
            Imprint: Group.IMPRINT,
            Series: Group.SERIES,
            Volume: Group.VOLUME,
            Folder: Group.FOLDER,
            StoryArc: Group.ARC,
            Comic: Group.COMIC,
        }
    )
)
FAVORITE_GROUP_CODE_MODELS: Final[MappingProxyType[str, type]] = MappingProxyType(
    {code: model for model, code in FAVORITE_MODEL_GROUP_CODES.items()}
)
FAVORITE_GROUP_CHOICES: Final = tuple(
    (group.value, GROUP_LABELS[group]) for group in FAVORITE_MODEL_GROUP_CODES.values()
)


class Favorite(BaseModel):
    """Per-user favorite tag for a browsable group or comic."""

    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    group = CharField(max_length=16, choices=FAVORITE_GROUP_CHOICES)
    target_id = PositiveIntegerField()

    class Meta(BaseModel.Meta):
        """Uniqueness across (user, group, target_id)."""

        unique_together = ("user", "group", "target_id")
