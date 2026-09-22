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
    # Keep vanished rows instead of deleting them.
    #
    # Set by the two filesystem scanners, the poller and the watcher,
    # because both *infer* their deletes from an observation of the
    # filesystem -- "the walk did not list it", "the OS said the name
    # went away" -- and #858 and #860 showed those claims can be lies.
    # A lie that hard-deletes costs the user their place in the book.
    #
    # Left False by the five producers that build their path sets from
    # the *database* rather than from disk -- LazyImporter, ForceUpdater,
    # adopt_folders, TagWriter and the janitor's failed_imports. None of
    # them populates a deleted set at all, so the flag is moot for them
    # today; it stays False so that if one ever grows a delete it must
    # opt in deliberately.
    #
    # Retention needs a way back, and the two scanners reach it
    # differently: the poller re-observes the whole library every pass
    # (``_unstamp_revived``), while the watcher relies on the importer's
    # own ``unstamp_revived`` phase, which probes the paths a task names.
    soft_delete: bool = False

    def total(self) -> int:
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
