"""Haystack Search index updater."""

from codex.librarian.search.tasks import (
    SearchIndexClearTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.search.update import FTSUpdateMixin


class SearchIndexerThread(FTSUpdateMixin):
    """A worker to handle search index update tasks."""

    def process_item(self, item):
        """Run the updater."""
        task = item
        if isinstance(task, SearchIndexUpdateTask):
            self.update_search_index(rebuild=task.rebuild)
        elif isinstance(task, SearchIndexRemoveStaleTask):
            self.remove_stale_records()
        elif isinstance(task, SearchIndexClearTask):
            self.clear_search_index()
        else:
            self.log.warning(f"Bad task sent to search index thread: {task}")
