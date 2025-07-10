"""Importer Create Statii."""

from abc import ABC

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterCreateStatus(ImporterStatus, ABC):
    """Importer Create Statii."""


class ImporterCreateTagsStatus(ImporterCreateStatus):
    """Importer Create Tags Status."""

    CODE = "ICT"
    VERB = "Create"
    ITEM_NAME = "tags"


class ImporterUpdateTagsStatus(ImporterCreateStatus):
    """Importer Create Tags Status."""

    CODE = "IUT"
    VERB = "Update"
    ITEM_NAME = "tags"


class ImporterCreateComicsStatus(ImporterCreateStatus):
    """Importer Create Comics Status."""

    CODE = "ICC"
    VERB = "Create"
    ITEM_NAME = "comics"


class ImporterUpdateComicsStatus(ImporterCreateStatus):
    """Importer Update Comics Status."""

    CODE = "IUC"
    VERB = "Update"
    ITEM_NAME = "comics"


class ImporterCreateCoversStatus(ImporterCreateStatus):
    """Importer Create Tags Status."""

    CODE = "ICV"
    VERB = "Create"
    ITEM_NAME = "custom covers"


class ImporterUpdateCoversStatus(ImporterCreateStatus):
    """Importer Updated Tags Status."""

    CODE = "IUV"
    VERB = "Update"
    ITEM_NAME = "custom covers"


CREATE_STATII = (
    ImporterCreateTagsStatus,
    ImporterUpdateTagsStatus,
    ImporterCreateComicsStatus,
    ImporterUpdateComicsStatus,
    ImporterCreateCoversStatus,
    ImporterUpdateCoversStatus,
)
