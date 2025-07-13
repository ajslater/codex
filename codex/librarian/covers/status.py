"""Cover status types."""

from abc import ABC

from codex.librarian.status import Status


class CoversStatus(Status, ABC):
    """Covers Status."""

    ITEM_NAME = "covers"


class CreateCoversStatus(CoversStatus):
    """Create Covers Status."""

    CODE = "CCC"
    VERB = "Create"


class RemoveCoversStatus(CoversStatus):
    """Purge Covers Status."""

    CODE = "CRC"
    VERB = "Remove"
    log_success = True


class FindOrphanCoversStatus(CoversStatus):
    """Find Orphan Covers Status."""

    CODE = "CFO"
    ITEM_NAME = "orphan covers"
    VERB = "Find"
    _verbed = "Found"


COVERS_STATII = (
    CreateCoversStatus,
    RemoveCoversStatus,
    FindOrphanCoversStatus,
)
