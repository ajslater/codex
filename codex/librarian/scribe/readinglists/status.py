"""Reading list statii."""

from abc import ABC

from codex.librarian.scribe.status import ScribeStatus


class ReadingListStatus(ScribeStatus, ABC):
    """Reading list statii."""


class ReadingListSyncStatus(ReadingListStatus):
    """Rebuild the lists that come from story-arc tags."""

    CODE = "RLS"
    VERB = "Sync"
    _verbed = "Synced"
    ITEM_NAME = "reading lists from tags"


class ReadingListFetchStatus(ReadingListStatus):
    """Fetch reading lists from the network."""

    CODE = "RLF"
    VERB = "Fetch"
    _verbed = "Fetched"
    ITEM_NAME = "reading lists"


class ReadingListImportStatus(ReadingListStatus):
    """Store fetched or uploaded reading lists."""

    CODE = "RLI"
    VERB = "Import"
    ITEM_NAME = "reading lists"


class ReadingListMatchStatus(ReadingListStatus):
    """Match reading list entries to comics."""

    CODE = "RLM"
    VERB = "Match"
    _verbed = "Matched"
    ITEM_NAME = "reading list issues"


READING_LIST_STATII = (
    ReadingListSyncStatus,
    ReadingListFetchStatus,
    ReadingListImportStatus,
    ReadingListMatchStatus,
)
