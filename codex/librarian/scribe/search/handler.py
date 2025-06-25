"""Handle search indexer tasks."""

from codex.librarian.scribe.search.tasks import (
    SearchIndexClearTask,
    SearchIndexerTask,
    SearchIndexOptimizeTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.scribe.search.update import SearchIndexerUpdate


class SearchIndexer(SearchIndexerUpdate):
    """Handle search indexer tasks."""

    def handle_task(self, task: SearchIndexerTask):
        """Handle search indexer tasks."""
        match task:
            case SearchIndexUpdateTask():
                self.update_search_index(rebuild=task.rebuild)
            case SearchIndexRemoveStaleTask():
                self.remove_stale_records()
            case SearchIndexOptimizeTask():
                self.optimize()
            case SearchIndexClearTask():
                self.clear_search_index()
            case _:
                self.log.warning(f"Bad task sent to scribe {task}")
