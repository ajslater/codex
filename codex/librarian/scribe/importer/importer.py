"""The main importer class."""

from codex.librarian.memory import get_mem_limit
from codex.librarian.scribe.importer.moved import MovedImporter
from codex.librarian.scribe.importer.pragmas import importer_pragmas
from codex.settings import IMPORTER_CHUNK_MEM_FRACTION

# Per-comic working set per chunk-resident path: Comic instance +
# LINK_FKS dict + LINK_M2MS sets + FTS payload + ORM cache overhead.
# Empirically ~6-12 KiB; round up to 16 KiB so the sizer leaves
# headroom on memory-constrained hosts.
_PER_COMIC_BYTES = 16 * 1024
# Floor stops chunk count from exploding on tiny hosts where the
# per-chunk SQL overhead would dominate the per-comic work.
_CHUNK_FLOOR = 1000
# Ceiling is a safety net against ``get_mem_limit`` returning a
# pathological value (misconfigured cgroup, broken sysconf, etc.) —
# not a cap on normal operation. 500k is well above any realistic
# library size, so a 32 / 64 GiB host stays in a single chunk for
# typical runs while a misreported 1 PiB host can't compute a
# stupendous chunk size that pessimizes recovery from abort.
_CHUNK_CEILING = 500000

_PRE_PHASES = ("init_apply", "move_and_modify_dirs")
_PER_COMIC_PHASES = ("read", "query", "create_and_update", "link")
_POST_PHASES = ("fail_imports", "delete", "full_text_search")


class ComicImporter(MovedImporter):
    """Initialize, run and finish a bulk import."""

    @staticmethod
    def _compute_chunk_size() -> int:
        """
        Size per-comic-phase chunks to fit available memory.

        Reads cgroups limits via :mod:`codex.librarian.memory` so a
        Docker / Pi container's memory cap is honored even when host
        RAM is much larger.
        """
        mem_budget = get_mem_limit("b") * IMPORTER_CHUNK_MEM_FRACTION
        raw = int(mem_budget // _PER_COMIC_BYTES)
        return max(_CHUNK_FLOOR, min(_CHUNK_CEILING, raw))

    def _run_phases(self, names: tuple[str, ...]) -> bool:
        """Run named phases in order. Return False if aborted mid-run."""
        for name in names:
            method = getattr(self, name)
            method()
            if self.abort_event.is_set():
                return False
        return True

    def _run_per_comic_phases_chunked(self) -> bool:
        """
        Chunk the per-comic phases to bound peak memory.

        ``read → query → create_and_update → link`` runs once per
        chunk of paths. Reference-data FK rows (Publisher, Imprint,
        Series, Volume, named tags) created in chunk N are visible to
        chunk N+1 because every FK ``bulk_create`` already uses
        ``update_conflicts=True`` — duplicate ``(library, name)`` keys
        from a parent that another chunk also referenced are
        idempotent UPSERTs, not failures.

        The combined ``files_created | files_modified`` set is
        partitioned into chunks of ``_compute_chunk_size`` paths each
        and fed back through ``self.task`` per iteration. Created vs
        modified is preserved per-chunk by intersecting with the
        original sets.
        """
        saved_created = self.task.files_created
        saved_modified = self.task.files_modified
        all_paths = saved_created | saved_modified

        if not all_paths:
            # Empty path case — still call the per-comic phases once
            # so cover-only and cleanup paths fire (covers_*
            # processing, status finalization).
            return self._run_phases(_PER_COMIC_PHASES)

        chunk_size = self._compute_chunk_size()
        # Sort once for deterministic chunk boundaries — useful for
        # log-diff debugging and for any future resume-from-watermark
        # work.
        path_list = sorted(all_paths)
        for start in range(0, len(path_list), chunk_size):
            if self.abort_event.is_set():
                return False
            chunk = frozenset(path_list[start : start + chunk_size])
            self.task.files_created = chunk & saved_created
            self.task.files_modified = chunk & saved_modified
            if not self._run_phases(_PER_COMIC_PHASES):
                return False
        return True

    def apply(self) -> None:
        """Bulk import comics."""
        try:
            self.abort_event.clear()
            # ``importer_pragmas`` bumps the page cache and defers
            # WAL checkpoints for the duration of the run, then
            # force-checkpoints + ``PRAGMA optimize`` on exit.
            with importer_pragmas():
                if not self._run_phases(_PRE_PHASES):
                    return
                if not self._run_per_comic_phases_chunked():
                    return
                self._run_phases(_POST_PHASES)
        finally:
            self.finish()
