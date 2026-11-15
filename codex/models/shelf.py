"""Shelf models: per-user named groupings of browsable targets."""

from types import MappingProxyType
from typing import Final, override

from django.conf import settings
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Index,
    PositiveIntegerField,
    UniqueConstraint,
)

from codex.choices.limits import MAX_NAME_LEN
from codex.collection import COLLECTION_LABELS, Collection
from codex.models.base import BaseModel
from codex.models.collections import Folder, Imprint, Publisher, Series, Volume
from codex.models.comic import Comic
from codex.models.named import StoryArc

__all__ = (
    "SHELF_COLLECTION_CHOICES",
    "SHELF_COLLECTION_MODELS",
    "SHELF_MODEL_COLLECTIONS",
    "Shelf",
    "ShelfItem",
)

# Single source of truth for the model ↔ collection dispatch. The collection
# code is the collection vocabulary (a :class:`Collection` member, whose value
# is the collection name) shared by the whole app. Every shelf-related
# view, signal, cron, and annotation pulls from these maps so the seven
# collections stay aligned across the codebase. Filter / annotation / API
# views consume the forward map; the cleanup cron and signal handler
# consume the reverse map. Both are immutable proxies.
SHELF_MODEL_COLLECTIONS: Final[MappingProxyType[type[BaseModel], Collection]] = (
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
SHELF_COLLECTION_MODELS: Final[MappingProxyType[str, type[BaseModel]]] = (
    MappingProxyType(
        {code.value: model for model, code in SHELF_MODEL_COLLECTIONS.items()}
    )
)
SHELF_COLLECTION_CHOICES: Final = tuple(
    (collection.value, COLLECTION_LABELS[collection])
    for collection in SHELF_MODEL_COLLECTIONS.values()
)


class Shelf(BaseModel):
    """
    A user's named shelf.

    Every shelf is equal: there are no built-in or special shelves, and
    the name is free text the user owns. It must never be reported by
    telemetry.
    """

    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    name = CharField(max_length=MAX_NAME_LEN)

    class Meta(BaseModel.Meta):
        """A user cannot have two shelves with the same name."""

        verbose_name_plural = "shelves"
        constraints = (
            UniqueConstraint(fields=("user", "name"), name="unique_shelf_user_name"),
        )

    @override
    def __repr__(self) -> str:
        return f"<Shelf pk={self.pk}>"


class ShelfItem(BaseModel):
    """One browsable collection row or comic placed on a shelf."""

    shelf = ForeignKey(Shelf, on_delete=CASCADE, related_name="items")
    collection = CharField(max_length=16, choices=SHELF_COLLECTION_CHOICES)
    target_id = PositiveIntegerField()

    class Meta(BaseModel.Meta):
        """A target sits on a shelf at most once."""

        constraints = (
            UniqueConstraint(
                fields=("shelf", "collection", "target_id"),
                name="unique_shelfitem_shelf_target",
            ),
        )
        indexes = (
            # Serves the target-deleted signal and the orphan sweep, which
            # look items up by target with no shelf in hand.
            Index(fields=("collection", "target_id"), name="shelfitem_target"),
        )
