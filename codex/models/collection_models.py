"""
Which model each browsable collection is, and back.

The browse collections a person can point at by pk: every one but the
synthetic root. Restore resolves stored routes through it; the live sync
and backups name a list's items by it.
"""

from types import MappingProxyType
from typing import Final

from codex.collection import Collection
from codex.models.base import BaseModel
from codex.models.collections import Folder, Imprint, Publisher, Series, Volume
from codex.models.comic import Comic
from codex.models.readinglist import ReadingList

__all__ = ("BROWSE_COLLECTION_MODELS", "BROWSE_MODEL_COLLECTIONS")

BROWSE_MODEL_COLLECTIONS: Final[MappingProxyType[type[BaseModel], Collection]] = (
    MappingProxyType(
        {
            Publisher: Collection.PUBLISHER,
            Imprint: Collection.IMPRINT,
            Series: Collection.SERIES,
            Volume: Collection.VOLUME,
            Folder: Collection.FOLDER,
            ReadingList: Collection.ARC,
            Comic: Collection.COMIC,
        }
    )
)
BROWSE_COLLECTION_MODELS: Final[MappingProxyType[str, type[BaseModel]]] = (
    MappingProxyType(
        {code.value: model for model, code in BROWSE_MODEL_COLLECTIONS.items()}
    )
)
