"""The main importer class."""

from time import time
from types import MappingProxyType

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.notifier.tasks import (
    FAILED_IMPORTS_CHANGED_TASK,
    LIBRARY_CHANGED_TASK,
)
from codex.librarian.scribe.importer.init import InitImporter
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.scribe.search.tasks import SearchIndexUpdateTask

_REPORT_MAP = MappingProxyType(
    {
        "folders": "folders imported",
        "tags": "tags imported",
        "covers": "custom covers imported",
        "link": "tags linked",
        "link_covers": "covers linked",
        "comics_deleted": "comics deleted",
        "tags_deleted": "tags deleted",
        "folders_deleted": "folders deleted",
        "folders_moved": "folders moved",
        "comics_moved": "comics moved",
        "covers_moved": " covers moved",
    }
)
_SEARCH_INDEX_STATII = (
    SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
)


class FinishImporter(InitImporter):
    """Initialize, run and finish a bulk import."""

    def finish(self):
        """Perform final tasks when the apply is done."""
        self.library.end_update()
        self.status_controller.finish_many(ImporterStatusTypes.values)
        elapsed_time = time() - self.start_time.timestamp()
        elapsed = naturaldelta(elapsed_time)
        if self.counts.changed():
            cache.clear()
            log_txt = f"Updated library {self.library.path} in {elapsed}."
            if self.counts.comic:
                cps = round(self.counts.comic / elapsed_time, 1)
                log_txt += f" Imported {self.counts.comic} at {cps} comics per second."
            else:
                log_txt += " No comics to import."
            for attr, suffix in _REPORT_MAP.items():
                if value := getattr(self.counts, attr):
                    log_txt += f" {value} {suffix}."

            self.librarian_queue.put(LIBRARY_CHANGED_TASK)

            if self.counts.search_changed():
                # Wait to start the search index update in case more updates are incoming.
                task = SearchIndexUpdateTask(rebuild=False)
                self.librarian_queue.put(task)
            else:
                self.status_controller.finish_many(_SEARCH_INDEX_STATII)
        else:
            log_txt = f"No updates neccissary for library {self.library.path}. Finished in {elapsed}."
            self.status_controller.finish_many(_SEARCH_INDEX_STATII)
        self.log.success(log_txt)
        if self.counts.failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_CHANGED_TASK)
