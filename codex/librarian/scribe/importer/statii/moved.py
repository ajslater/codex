"""Importer Moved Statii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterMoveStatus(ImporterStatus, ABC):
    """Importer Moved Status."""

    VERB = "Move"


class ImporterMoveFoldersStatus(ImporterMoveStatus):
    """Importer Moved Folder Status."""

    CODE = "IMF"
    ITEM_NAME = "folders"


class ImporterMoveComicsStatus(ImporterMoveStatus):
    """Importer Moved Comics Status."""

    CODE = "IMC"
    ITEM_NAME = "comics"


class ImporterMoveCoversStatus(ImporterMoveStatus):
    """Importer Moved Covers Status."""

    CODE = "IMV"
    ITEM_NAME = "custom covers"


MOVED_STATII = (
    ImporterMoveFoldersStatus,
    ImporterMoveComicsStatus,
    ImporterMoveCoversStatus,
)
