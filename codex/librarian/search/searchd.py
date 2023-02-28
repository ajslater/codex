"""Haystack Search index updater."""
from codex.librarian.search.optimize import OptimizeMixin
from codex.librarian.search.tasks import (
    SearchIndexOptimizeTask,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexUpdateTask,
)
from codex.librarian.search.update import UpdateMixin


class SearchIndexerThread(UpdateMixin, OptimizeMixin):
    """A worker to handle search index update tasks."""

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            self._rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexUpdateTask):
            self._update_search_index(rebuild=task.rebuild)
        elif isinstance(task, SearchIndexOptimizeTask):
            self._optimize_search_index(task.force)
        else:
            self.log.warning(f"Bad task sent to search index thread: {task}")
