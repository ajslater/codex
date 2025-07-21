"""Importer Failed Imports Sattii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterFailedImportStatus(ImporterStatus, ABC):
    """Importer Failed Imports Statii."""

    ITEM_NAME = "failed imports"


class ImporterFailedImportsQueryStatus(ImporterFailedImportStatus, ABC):
    """Importer Failed Imports Query Statii."""

    CODE = "IFQ"
    VERB = "Query"
    _verbed = "Queried"


class ImporterFailedImportsUpdateStatus(ImporterFailedImportStatus, ABC):
    """Importer Failed Imports Update Statii."""

    CODE = "IFU"
    VERB = "Update"


class ImporterFailedImportsCreateStatus(ImporterFailedImportStatus, ABC):
    """Importer Failed Imports Create Statii."""

    CODE = "IFC"
    VERB = "Mark Failed"
    _verbed = "Marked Failed"


class ImporterFailedImportsDeleteStatus(ImporterFailedImportStatus, ABC):
    """Importer Failed Imports Create Statii."""

    CODE = "IFD"
    VERB = "Clean up"
    _verbed = "Cleaned up"


FAILED_IMPORTS_STATII = (
    ImporterFailedImportsQueryStatus,
    ImporterFailedImportsUpdateStatus,
    ImporterFailedImportsCreateStatus,
    ImporterFailedImportsDeleteStatus,
)
