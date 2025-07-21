"""Handle search indexer tasks."""

from codex.librarian.scribe.search.sync import SearchIndexerSync
from codex.librarian.scribe.search.tasks import (
    SearchIndexCleanStaleTask,
    SearchIndexClearTask,
    SearchIndexerTask,
    SearchIndexOptimizeTask,
    SearchIndexSyncTask,
)


class SearchIndexer(SearchIndexerSync):
    """Handle search indexer tasks."""

    def handle_task(self, task: SearchIndexerTask):
        """Handle search indexer tasks."""
        match task:
            case SearchIndexSyncTask():
                self.update_search_index(rebuild=task.rebuild)
            case SearchIndexCleanStaleTask():
                self.remove_stale_records()
            case SearchIndexOptimizeTask():
                self.optimize()
            case SearchIndexClearTask():
                self.clear_search_index()
            case _:
                self.log.warning(f"Bad task sent to scribe {task}")
