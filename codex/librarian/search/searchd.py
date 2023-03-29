"""Haystack Search index updater."""
from codex.librarian.search.merge import MergeMixin
from codex.librarian.search.tasks import (
    SearchIndexMergeTask,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.search.update import UpdateMixin


class SearchIndexerThread(UpdateMixin, MergeMixin):
    """A worker to handle search index update tasks."""

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            self.rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexUpdateTask):
            self.update_search_index(rebuild=task.rebuild)
        elif isinstance(task, SearchIndexMergeTask):
            self.merge_search_index(task.optimize)
        elif isinstance(task, SearchIndexRemoveStaleTask):
            self.remove_stale_records()
        else:
            self.log.warning(f"Bad task sent to search index thread: {task}")
