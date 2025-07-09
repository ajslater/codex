"""Importer Read Statii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterReadStatus(ImporterStatus, ABC):
    """Importer Read Statii."""

    ITEM_NAME = "comics"


class ImporterReadComicsStatus(ImporterReadStatus):
    """Importer Read Status."""

    CODE = "IRT"
    VERB = "Read tags from"
    _verbed = "Read tags from"


class ImporterAggregateStatus(ImporterReadStatus):
    """Importer Aggregate Status."""

    CODE = "IAT"
    VERB = "Aggregate tags from"
    _verbed = "Aggregated tags from"


READ_STATII = (ImporterReadComicsStatus, ImporterAggregateStatus)
