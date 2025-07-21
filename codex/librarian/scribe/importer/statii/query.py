"""Importer Query Statii."""

from codex.librarian.scribe.importer.status import ImporterStatus


class ImporterQueryStatus(ImporterStatus):
    """Importer Query Statii."""

    VERB = "Query"
    _verbed = "Queried"


class ImporterQueryMissingTagsStatus(ImporterQueryStatus):
    """Importer Aggregate Status."""

    CODE = "IQT"
    ITEM_NAME = "missing tags"


class ImporterQueryComicUpdatesStatus(ImporterQueryStatus):
    """Importer Comic Updates Status."""

    CODE = "IQC"
    ITEM_NAME = "comics"


class ImporterQueryTagLinksStatus(ImporterQueryStatus):
    """Importer Tag Links Status."""

    CODE = "IQL"
    ITEM_NAME = "tag links"


class ImporterQueryMissingCoversStatus(ImporterQueryStatus):
    """Importer Missing Covers Status."""

    CODE = "IQV"
    ITEM_NAME = "missing custom covers"


QUERY_STATII = (
    ImporterQueryMissingTagsStatus,
    ImporterQueryComicUpdatesStatus,
    ImporterQueryTagLinksStatus,
    ImporterQueryMissingCoversStatus,
)
