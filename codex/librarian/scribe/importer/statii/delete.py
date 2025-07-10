"""Importer Remove Sattii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterRemoveStatus(ImporterStatus, ABC):
    """Importer Remove Sattii."""

    VERB = "Remove"


class ImporterRemoveFoldersStatus(ImporterRemoveStatus):
    """Importer Remove Folders Status."""

    CODE = "IRF"
    ITEM_NAME = "folders"


class ImporterRemoveComicsStatus(ImporterRemoveStatus):
    """Importer Remove Comics Status."""

    CODE = "IRC"
    ITEM_NAME = "comics"


class ImporterRemoveCoversStatus(ImporterRemoveStatus):
    """Importer Remove Covers Status."""

    CODE = "IRV"
    ITEM_NAME = "custom covers"


REMOVE_STATII = (
    ImporterRemoveFoldersStatus,
    ImporterRemoveComicsStatus,
    ImporterRemoveCoversStatus,
)
