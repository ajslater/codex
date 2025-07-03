"""Sync the fts index with the imported database."""

from codex.librarian.scribe.importer.search.prepare import (
    SearchIndexPrepareImporter,
)
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.scribe.search.handler import SearchIndexer
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status

_STATII = (
    Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAN),
    Status(ImporterStatusTypes.SEARCH_INDEX_UPDATE),
    Status(ImporterStatusTypes.SEARCH_INDEX_CREATE),
)


class SearchIndexImporter(SearchIndexPrepareImporter):
    """Sync the fts index with the imported database."""

    def clean_fts(self) -> int:
        """Clean search index of any deleted comics."""
        indexer = SearchIndexer(
            self.log, self.librarian_queue, self.db_write_lock, event=self.abort_event
        )
        return indexer.remove_stale_records()

    def full_text_search(self):
        """Sync the fts index with the imported database."""
        self.status_controller.start_many(_STATII)
        try:
            count = self.clean_fts()
            self.import_search_index(count)
        finally:
            self.status_controller.finish_many(_STATII)
