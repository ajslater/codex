"""Shelf models: per-user named groupings of browsable targets."""

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
from codex.collection import COLLECTION_LABELS
from codex.models.base import BaseModel
from codex.models.collection_models import (
    BROWSE_COLLECTION_MODELS,
    BROWSE_MODEL_COLLECTIONS,
)

__all__ = (
    "SHELF_COLLECTION_CHOICES",
    "SHELF_COLLECTION_MODELS",
    "SHELF_MODEL_COLLECTIONS",
    "Shelf",
    "ShelfItem",
)

# Moved to codex.models.collection_models; aliased here until shelves go.
SHELF_MODEL_COLLECTIONS: Final = BROWSE_MODEL_COLLECTIONS
SHELF_COLLECTION_MODELS: Final = BROWSE_COLLECTION_MODELS
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
