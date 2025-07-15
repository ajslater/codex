"""Sync the fts index with the imported database."""

from codex.librarian.scribe.importer.search.prepare import (
    SearchIndexPrepareImporter,
)
from codex.librarian.scribe.importer.statii.search import (
    ImporterFTSCreateStatus,
    ImporterFTSUpdateStatus,
)
from codex.librarian.scribe.search.handler import SearchIndexer
from codex.librarian.scribe.search.status import SearchIndexCleanStatus

_STATII = (SearchIndexCleanStatus, ImporterFTSCreateStatus, ImporterFTSUpdateStatus)


class SearchIndexImporter(SearchIndexPrepareImporter):
    """Sync the fts index with the imported database."""

    def clean_fts(self) -> int:
        """Clean search index of any deleted comics."""
        indexer = SearchIndexer(
            self.log, self.librarian_queue, self.db_write_lock, event=self.abort_event
        )
        return indexer.remove_stale_records(log_success=False)

    def full_text_search(self):
        """Sync the fts index with the imported database."""
        statii = (status_class() for status_class in _STATII)
        self.status_controller.start_many(statii)
        try:
            count = self.clean_fts()
            self.import_search_index(count)
        finally:
            self.status_controller.finish_many(statii)
