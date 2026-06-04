"""Librarian Status for scribe bulk writes."""

from abc import ABC

from codex.librarian.status import Status


class ScribeStatus(Status, ABC):
    """Scribe Statii."""


class UpdateCollectionTimestampsStatus(ScribeStatus):
    """Update Collection Timestamps Status."""

    CODE = "IGU"
    ITEM_NAME = "browser collections"
    VERB = "Update timestamps for"
    _verbed = "Updated timestamps for"


class TagWriteStatus(ScribeStatus):
    """Tag Write Status."""

    CODE = "TWR"
    ITEM_NAME = "comic tags"
    VERB = "Write"
    _verbed = "Wrote"


SCRIBE_STATII = (UpdateCollectionTimestampsStatus, TagWriteStatus)
