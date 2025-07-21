"""Search Index Sync Statii."""

from abc import ABC

from codex.librarian.scribe.status import ScribeStatus


class SearchIndexStatus(ScribeStatus, ABC):
    """Search Index Sync Statii."""


class SearchIndexClearStatus(SearchIndexStatus):
    """Search Index Clear Status."""

    CODE = "SIX"
    VERB = "Clear"
    _verbed = "Cleared"
    ITEM_NAME = "full text search table"
    SINGLE = True
    log_success = True


class SearchIndexCleanStatus(SearchIndexStatus):
    """Search Index Clean Status."""

    CODE = "SIR"
    VERB = "Clean"
    _verbed = "Cleaned"
    ITEM_NAME = "orphan search entries"


class SearchIndexOptimizeStatus(SearchIndexStatus):
    """Search Index Optimize Status."""

    CODE = "SIO"
    VERB = "Optimize"
    ITEM_NAME = "search virtual table"
    SINGLE = True
    log_success = True


class SearchIndexSyncUpdateStatus(SearchIndexStatus):
    """Search Index Sync Update Status."""

    CODE = "SSU"
    VERB = "Sync"
    _verbed = "Synced"
    ITEM_NAME = "old search entries"


class SearchIndexSyncCreateStatus(SearchIndexStatus):
    """Search Index Sync Create Status."""

    CODE = "SSC"
    VERB = "Sync"
    _verbed = "Synced"
    ITEM_NAME = "new search entries"


SEARCH_INDEX_STATII = (
    SearchIndexClearStatus,
    SearchIndexCleanStatus,
    SearchIndexOptimizeStatus,
    SearchIndexSyncUpdateStatus,
    SearchIndexSyncCreateStatus,
)
