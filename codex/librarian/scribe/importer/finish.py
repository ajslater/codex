"""The main importer class."""

from time import time
from types import MappingProxyType

from django.core.cache import cache
from humanize import intcomma, naturaldelta

from codex.librarian.notifier.tasks import (
    FAILED_IMPORTS_CHANGED_TASK,
    LIBRARY_CHANGED_TASK,
)
from codex.librarian.scribe.importer.init import InitImporter
from codex.librarian.scribe.importer.statii import IMPORTER_STATII
from codex.librarian.scribe.search.status import SEARCH_INDEX_STATII
from codex.librarian.scribe.status import SCRIBE_STATII

_REPORT_MAP = MappingProxyType(
    {
        "comics_moved": "comics moved",
        "folders_moved": "folders moved",
        "covers_moved": " covers moved",
        "comic": "comics imported",
        "folders": "folders imported",
        "tags": "tags imported",
        "covers": "custom covers imported",
        "link": "tags linked",
        "link_covers": "covers linked",
        "comics_deleted": "comics deleted",
        "tags_deleted": "tags deleted",
        "folders_deleted": "folders deleted",
    }
)
_FINISH_STATII = (*IMPORTER_STATII, *SEARCH_INDEX_STATII, *SCRIBE_STATII)


class FinishImporter(InitImporter):
    """Initialize, run and finish a bulk import."""

    def finish(self):
        """Perform final tasks when the apply is done."""
        if self.abort_event.is_set():
            self.log.info("Import task aborted early.")
        self.abort_event.clear()
        self.library.end_update()
        self.status_controller.finish_many(_FINISH_STATII)
        elapsed_time = time() - self.start_time.timestamp()
        elapsed = naturaldelta(elapsed_time)
        if self.counts.changed():
            cache.clear()
            log_txt = f"Imported library {self.library.path} in {elapsed}"
            if self.counts.comic:
                cps = round(self.counts.comic / elapsed_time, 1)
                cps = intcomma(cps)
                log_txt += f" at {cps} comics per second"
            else:
                log_txt += " but no comics were imported"
            log_txt += "."

            for attr, suffix in _REPORT_MAP.items():
                if value := getattr(self.counts, attr):
                    value = intcomma(value)
                    log_txt += f" {value} {suffix}."

            self.librarian_queue.put(LIBRARY_CHANGED_TASK)
        else:
            log_txt = f"No updates necessary for library {self.library.path}. Finished in {elapsed}."
        self.log.success(log_txt)
        if self.counts.failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_CHANGED_TASK)
