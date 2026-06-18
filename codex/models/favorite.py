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

from codex.collection import COLLECTION_LABELS, Collection
from codex.models.base import BaseModel
from codex.models.collections import Folder, Imprint, Publisher, Series, Volume
from codex.models.comic import Comic
from codex.models.named import StoryArc

__all__ = (
    "FAVORITE_COLLECTION_CHOICES",
    "FAVORITE_COLLECTION_MODELS",
    "FAVORITE_MODEL_COLLECTIONS",
    "Favorite",
)

# Single source of truth for the model ↔ collection dispatch. The collection
# code is the collection vocabulary (a :class:`Collection` member, whose value
# is the collection name) shared by the whole app. Every favorite-related
# view, signal, cron, and annotation pulls from these maps so the seven
# collections stay aligned across the codebase. Filter / annotation / API
# views consume the forward map; the cleanup cron and signal handler
# consume the reverse map. Both are immutable proxies.
FAVORITE_MODEL_COLLECTIONS: Final[MappingProxyType[type[BaseModel], Collection]] = (
    MappingProxyType(
        {
            Publisher: Collection.PUBLISHER,
            Imprint: Collection.IMPRINT,
            Series: Collection.SERIES,
            Volume: Collection.VOLUME,
            Folder: Collection.FOLDER,
            StoryArc: Collection.ARC,
            Comic: Collection.COMIC,
        }
    )
)
FAVORITE_COLLECTION_MODELS: Final[MappingProxyType[str, type]] = MappingProxyType(
    {code: model for model, code in FAVORITE_MODEL_COLLECTIONS.items()}
)
FAVORITE_COLLECTION_CHOICES: Final = tuple(
    (collection.value, COLLECTION_LABELS[collection])
    for collection in FAVORITE_MODEL_COLLECTIONS.values()
)


class Favorite(BaseModel):
    """Per-user favorite tag for a browsable collection or comic."""

    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    collection = CharField(max_length=16, choices=FAVORITE_COLLECTION_CHOICES)
    target_id = PositiveIntegerField()

    class Meta(BaseModel.Meta):
        """Uniqueness across (user, collection, target_id)."""

        unique_together = ("user", "collection", "target_id")
