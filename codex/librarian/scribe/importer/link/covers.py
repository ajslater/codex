"""
Link Covers — vestigial passthrough.

Custom covers are uploaded directly via the admin endpoint, which sets
``GroupModel.custom_cover`` in the same transaction as the upload. The
watcher-driven sort-name-or-path linker that used to live here is gone.
"""

from codex.librarian.scribe.importer.failed.failed import FailedImportsImporter


class LinkCoversImporter(FailedImportsImporter):
    """Kept only as an inheritance step for ``LinkComicsImporterPrepare``."""

    def link_custom_covers(self) -> int:
        """Watcher no longer creates custom covers; nothing to link."""
        return 0
