"""The main importer class."""

from codex.librarian.scribe.importer.moved import MovedImporter

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

    def apply(self):
        """Bulk import comics."""
        try:
            self.abort_event.clear()
            for name in _METHODS:
                method = getattr(self, name)
                method()
                if self.abort_event.is_set():
                    return
        finally:
            self.finish()
