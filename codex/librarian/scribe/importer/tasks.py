"""DB Import Tasks."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from codex.librarian.scribe.tasks import ScribeTask


@dataclass
class ImportTask(ScribeTask):
    """For sending to the importer."""

    PRIORITY = 100

    library_id: int

    dirs_moved: Mapping[str, str] = field(default_factory=dict)
    dirs_modified: frozenset[str] = frozenset()
    # dirs_created: frozenset[str] | None = frozenset() # noqa: ERA001
    dirs_deleted: frozenset[str] = frozenset()

    files_moved: Mapping[str, str] = field(default_factory=dict)
    files_modified: frozenset[str] = frozenset()
    files_created: frozenset[str] = frozenset()
    files_deleted: frozenset[str] = frozenset()

    covers_moved: Mapping[str, str] = field(default_factory=dict)
    covers_modified: frozenset[str] = frozenset()
    covers_created: frozenset[str] = frozenset()
    covers_deleted: frozenset[str] = frozenset()

    force_import_metadata: bool = False
    check_metadata_mtime: bool = True

    def total(self):
        """Total number of operations."""
        return (
            len(self.dirs_moved)
            + len(self.dirs_modified)
            + len(self.dirs_deleted)
            + len(self.files_moved)
            + len(self.files_modified)
            + len(self.files_created)
            + len(self.files_deleted)
            + len(self.covers_moved)
            + len(self.covers_modified)
            + len(self.covers_created)
            + len(self.covers_deleted)
        )
