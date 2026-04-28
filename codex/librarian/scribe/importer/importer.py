"""The main importer class."""

from codex.librarian.scribe.importer.moved import MovedImporter
from codex.librarian.scribe.importer.pragmas import importer_pragmas

_METHODS = (
    "init_apply",
    "move_and_modify_dirs",
    "read",
    "query",
    "create_and_update",
    "link",
    "fail_imports",
    "delete",
    "full_text_search",
)


class ComicImporter(MovedImporter):
    """Initialize, run and finish a bulk import."""

    def apply(self) -> None:
        """Bulk import comics."""
        try:
            self.abort_event.clear()
            # ``importer_pragmas`` bumps the page cache and defers
            # WAL checkpoints for the duration of the run, then
            # force-checkpoints + ``PRAGMA optimize`` on exit.
            with importer_pragmas():
                for name in _METHODS:
                    method = getattr(self, name)
                    method()
                    if self.abort_event.is_set():
                        return
        finally:
            self.finish()
