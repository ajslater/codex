"""Librarian Status for scribe bulk writes."""

from abc import ABC

from codex.librarian.status import Status


class ScribeStatus(Status, ABC):
    """Scribe Statii."""


class UpdateGroupTimestampsStatus(ScribeStatus):
    """Update Group Timestamps Status."""

    CODE = "IGU"
    ITEM_NAME = "browser groups"
    VERB = "Update timestamps for"
    _verbed = "Updated timestamps for"


SCRIBE_STATII = (UpdateGroupTimestampsStatus,)
