"""The main importer class."""

from operator import itemgetter
from time import time
from types import MappingProxyType

from django.core.cache import cache
from django.db.models.functions import Now
from humanize import intcomma, naturaldelta

from codex.librarian.notifier.tasks import (
    FAILED_IMPORTS_CHANGED_TASK,
    LIBRARY_CHANGED_TASK,
    PENDING_DELETES_CHANGED_TASK,
)
from codex.librarian.pending_deletes import publish_revival
from codex.librarian.scribe.importer.init import InitImporter
from codex.librarian.scribe.importer.statii import IMPORTER_STATII
from codex.librarian.scribe.search.status import SEARCH_INDEX_STATII
from codex.librarian.scribe.status import SCRIBE_STATII
from codex.models.comic import Comic

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
        "comics_missing": "comics missing",
        "folders_missing": "folders missing",
        "comics_revived": "comics came back",
        "folders_revived": "folders came back",
    }
)
_FINISH_STATII = (*IMPORTER_STATII, *SEARCH_INDEX_STATII, *SCRIBE_STATII)


class FinishImporter(InitImporter):
    """Initialize, run and finish a bulk import."""

    def _get_log_finish_changed_text(self, elapsed, elapsed_time) -> str:
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

        return log_txt

    def _log_phase_times(self) -> None:
        """Log each phase's accumulated wall time, largest share first."""
        # Dotted "phase.step" sub-steps already count inside their
        # parent phase, so only top-level phases sum to the total.
        total = sum(secs for name, secs in self.phase_times.items() if "." not in name)
        if not total:
            return
        parts = ", ".join(
            f"{name} {secs:.2f}s ({secs / total:.0%})"
            for name, secs in sorted(
                self.phase_times.items(), key=itemgetter(1), reverse=True
            )
        )
        self.log.debug(f"Import phase times: {parts}")

    def _log_finish(self) -> None:
        """Log Finish."""
        elapsed_time = time() - self.start_time.timestamp()
        elapsed = naturaldelta(elapsed_time)
        if self.counts.changed():
            log_txt = self._get_log_finish_changed_text(elapsed, elapsed_time)
        else:
            log_txt = f"No updates necessary for library {self.library.path}. Finished in {elapsed}."
        self.log.success(log_txt)
        self._log_phase_times()

    def _stamp_metadata_imported(self) -> None:
        """
        Mark every comic this forced import pass touched as import-complete.

        Path-scoped so it covers SKIPPED no-metadata comics that never reach
        the per-comic write path. Idempotent (``__isnull=True``) and gated on
        ``force_import_metadata`` so ordinary watcher-driven imports never
        rewrite the column.
        """
        if not self.task.force_import_metadata:
            return
        if not (paths := self.metadata_import_paths):
            return
        Comic.objects.filter(
            library=self.library,
            path__in=paths,
            metadata_imported_at__isnull=True,
        ).update(metadata_imported_at=Now())

    def finish(self) -> None:
        """Perform final tasks when the apply is done."""
        if self.abort_event.is_set():
            self.log.info("Import task aborted early.")
        self.abort_event.clear()
        self._stamp_metadata_imported()
        self.library.end_update()
        self.status_controller.finish_many(_FINISH_STATII)
        self._log_finish()
        if self.counts.failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_CHANGED_TASK)
        self._notify_pending_deletes()

    def _notify_pending_deletes(self) -> None:
        """
        Tell the admin panel that the held set moved, either way.

        Published here rather than from the phases that do the work, so
        both sides land after the import's writes are done and in one
        place.

        The stamp side had no notification at all: ``comics_missing``
        was counted and logged but nothing told the Pending Deletes
        panel, so rows appeared there only on a Libraries-tab reload
        even though the websocket half was already wired.

        The revival side needs more than ``LIBRARY_CHANGED_TASK``, which
        ``_log_finish`` already sends: ``publish_revival`` also drops the
        zero-byte cover sentinel a render that failed while the file was
        missing left behind, which would otherwise leave a revived comic
        permanently blank. The duplicate ``LIBRARY_CHANGED_TASK`` it
        sends costs nothing -- the notifier dedupes on message text.
        """
        counts = self.counts
        if self.revived_comic_pks or counts.folders_revived:
            publish_revival(self.librarian_queue, self.revived_comic_pks)
        elif counts.comics_missing or counts.folders_missing:
            self.librarian_queue.put(PENDING_DELETES_CHANGED_TASK)
