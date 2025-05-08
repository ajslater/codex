"""Haystack Search index updater."""

from typing_extensions import override

from codex.librarian.search.tasks import (
    SearchIndexClearTask,
    SearchIndexOptimizeTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.search.update import SearchFTSUpdateThread


class SearchIndexerThread(SearchFTSUpdateThread):
    """A worker to handle search index update tasks."""

    @override
    def process_item(self, item):
        """Run the updater."""
        task = item
        match task:
            case SearchIndexUpdateTask():
                self.update_search_index(rebuild=task.rebuild)
            case SearchIndexRemoveStaleTask():
                self.remove_stale_records()
            case SearchIndexOptimizeTask():
                self.optimize(task.janitor)
            case SearchIndexClearTask():
                self.clear_search_index()
            case _:
                self.log.warning(f"Bad task sent to search index thread: {task}")
