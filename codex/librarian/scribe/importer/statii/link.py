"""Importer Link Statii."""

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterLinkStatus(ImporterStatus):
    """Importer Link Statii."""

    VERB = "Link"
    _verbed = "Linked"


class ImporterLinkTagsStatus(ImporterLinkStatus):
    """Importer Link Tags Status."""

    CODE = "ILT"
    ITEM_NAME = "tags"


class ImporterLinkCoversStatus(ImporterLinkStatus):
    """Importer Link Covers Status."""

    CODE = "ILV"
    ITEM_NAME = "custom covers"


LINK_STATII = (ImporterLinkTagsStatus, ImporterLinkCoversStatus)
