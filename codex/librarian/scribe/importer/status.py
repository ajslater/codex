"""Librarian Status for scribe bulk writes."""

from abc import ABC

from codex.librarian.scribe.status import ScribeStatus


class ImporterStatus(ScribeStatus, ABC):
    """Importer Status."""


class ImporterFailedImportsStatus(ImporterStatus):
    """Importer Failed Imports Status."""

    CODE = "IFI"
    VERB = "Mark"
    _verbed = "Marked"
    ITEM_NAME = "failed imports"


FAILED_IMPORTS_STATII = (ImporterFailedImportsStatus,)
