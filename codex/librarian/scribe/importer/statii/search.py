"""Importer Search Index Statii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterFTSStatus(ImporterStatus, ABC):
    """Importer Search Index Statii."""

    ITEM_NAME = "search index entries"


class ImporterFTSUpdateStatus(ImporterFTSStatus):
    """Importer Update Search Index Status."""

    CODE = "ISU"
    VERB = "Update"


class ImporterFTSCreateStatus(ImporterFTSStatus):
    """Importer Update Search Index Status."""

    CODE = "ISC"
    VERB = "Create"


IMPORTER_SEARCH_INDEX_STATII = (ImporterFTSUpdateStatus, ImporterFTSCreateStatus)
