"""Initialize Importer."""

from dataclasses import asdict, dataclass
from multiprocessing.queues import Queue
from pathlib import Path
from time import sleep, time
from typing import Any

from django.utils.timezone import now

from codex.librarian.covers.status import CreateCoversStatus
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateComicsStatus,
    ImporterCreateCoversStatus,
    ImporterCreateTagsStatus,
    ImporterUpdateComicsStatus,
    ImporterUpdateCoversStatus,
    ImporterUpdateTagsStatus,
)
from codex.librarian.scribe.importer.statii.delete import (
    ImporterRemoveComicsStatus,
    ImporterRemoveCoversStatus,
    ImporterRemoveFoldersStatus,
)
from codex.librarian.scribe.importer.statii.link import (
    ImporterLinkCoversStatus,
    ImporterLinkTagsStatus,
)
from codex.librarian.scribe.importer.statii.moved import (
    ImporterMoveComicsStatus,
    ImporterMoveCoversStatus,
    ImporterMoveFoldersStatus,
    ImporterUpdateFoldersStatus,
)
from codex.librarian.scribe.importer.statii.query import (
    ImporterQueryComicUpdatesStatus,
    ImporterQueryMissingCoversStatus,
    ImporterQueryMissingTagsStatus,
    ImporterQueryTagLinksStatus,
)
from codex.librarian.scribe.importer.statii.read import (
    ImporterAggregateStatus,
    ImporterReadComicsStatus,
)
from codex.librarian.scribe.importer.statii.search import (
    ImporterFTSCreateStatus,
    ImporterFTSUpdateStatus,
)
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.search.status import SearchIndexCleanStatus
from codex.librarian.scribe.status import UpdateGroupTimestampsStatus
from codex.librarian.worker import WorkerStatusBase
from codex.models import Library
from codex.settings import LOGLEVEL

_WRITE_WAIT_EXPIRY = 60


@dataclass
class Counts:
    """Total counts of operations."""

    comic: int = 0
    tags: int = 0
    link: int = 0
    link_covers: int = 0
    folders: int = 0
    comics_deleted: int = 0
    folders_deleted: int = 0
    tags_deleted: int = 0
    covers: int = 0
    covers_deleted: int = 0
    comics_moved: int = 0
    folders_moved: int = 0
    covers_moved: int = 0
    failed_imports: int = 0

    def _any(self, exclude_prefixes: tuple[str, ...]) -> bool:
        return any(
            value
            for key, value in asdict(self).items()
            if not key.startswith(exclude_prefixes)
        )

    def changed(self):
        """Anything changed at all."""
        return self._any(("failed",))

    def search_changed(self):
        """Is the search index be out of date."""
        return self._any(
            (
                "cover",
                "failed",
            )
        )


class InitImporter(WorkerStatusBase):
    """Initial Importer."""

    def __init__(
        self, task: ImportTask, logger_, librarian_queue: Queue, db_write_lock, event
    ) -> None:
        """Initialize the import."""
        super().__init__(logger_, librarian_queue, db_write_lock)
        self.task: ImportTask = task
        self.metadata: dict[str, Any] = {}
        self.counts = Counts()
        # Per-chunk accumulator for the comic-cover-create task. Both
        # ``create_comics`` (newly-inserted Comics) and ``update_comics``
        # (existing Comics whose covers were just purged by
        # ``remove_covers``) add their pks here; ``create_and_update``
        # submits a single ``CoverCreateTask`` with the union so the
        # cover thread runs one ``CreateCoversStatus`` start/finish per
        # chunk instead of two. Held off ``metadata`` because it's
        # operational state, not parsed comic data — keeps the metadata
        # fixture-comparable in tests.
        self.cover_create_pks: set[int] = set()
        self.library = Library.objects.only("path").get(pk=self.task.library_id)
        self.abort_event = event
        self.start_time = now()
        self._is_log_debug_task = (
            self.log.level(LOGLEVEL).no <= self.log.level("DEBUG").no
        )

    def _wait_for_filesystem_ops_to_finish(self) -> bool:
        """Watcher sends events before filesystem events finish, so wait for them."""
        started_checking = time()

        # Don't wait for deletes to complete.
        # Do wait for move, modified, create files before import.
        all_modified_paths = (
            frozenset(self.task.dirs_moved.values())
            | frozenset(self.task.files_moved.values())
            | self.task.dirs_modified
            | self.task.files_modified
            | self.task.files_created
        )

        old_total_size = -1
        total_size = 0
        wait_time = 2
        while old_total_size != total_size:
            if old_total_size > 0:
                # second time around or more
                sleep(wait_time)
                wait_time = wait_time**2
                reason = (
                    f"Waiting for files to copy before import: "
                    f"{old_total_size} != {total_size}"
                )
                self.log.debug(reason)
            if time() - started_checking > _WRITE_WAIT_EXPIRY:
                return True

            old_total_size = total_size
            total_size = 0
            for path_str in all_modified_paths:
                path = Path(path_str)
                if path.exists():
                    total_size += path.stat().st_size
        return False

    #######
    # LOG #
    #######
    def _log_task_construct_dirs_log(self) -> list:
        """Construct dirs log line."""
        dirs_log = []
        if self.task.dirs_moved:
            dirs_log += [f"{len(self.task.dirs_moved)} moved"]
        if self.task.dirs_modified:
            dirs_log += [f"{len(self.task.dirs_modified)} modified"]
        if self.task.dirs_deleted:
            dirs_log += [f"{len(self.task.dirs_deleted)} deleted"]
        return dirs_log

    def _log_task_construct_comics_log(self) -> list:
        """Construct comcis log line."""
        comics_log = []
        if self.task.files_moved:
            comics_log += [f"{len(self.task.files_moved)} moved"]
        if self.task.files_modified:
            comics_log += [f"{len(self.task.files_modified)} modified"]
        if self.task.files_created:
            comics_log += [f"{len(self.task.files_created)} created"]
        if self.task.files_deleted:
            comics_log += [f"{len(self.task.files_deleted)} deleted"]
        return comics_log

    def _log_task(self) -> None:
        """Log the fs watcher event self.task."""
        if not self._is_log_debug_task:
            return

        self.log.debug(f"Updating library {self.library.path}...")
        comics_log = self._log_task_construct_comics_log()
        if comics_log:
            log = "Comics: "
            log += ", ".join(comics_log)
            self.log.debug("  " + log)

        dirs_log = self._log_task_construct_dirs_log()
        if dirs_log:
            log = "Folders: "
            log += ", ".join(dirs_log)
            self.log.debug("  " + log)

    ########
    # INIT #
    ########
    def _init_librarian_status_moved(self, status_list) -> int:
        """Initialize moved statuses."""
        search_index_updates = 0
        if self.task.dirs_moved:
            status_list += [ImporterMoveFoldersStatus(None, len(self.task.dirs_moved))]
        if self.task.files_moved:
            status_list += [ImporterMoveComicsStatus(None, len(self.task.files_moved))]
            search_index_updates += len(self.task.files_moved)
        if self.task.covers_moved:
            status_list += [ImporterMoveCoversStatus(None, len(self.task.covers_moved))]
        if self.task.dirs_modified:
            status_list += [
                ImporterUpdateFoldersStatus(None, len(self.task.dirs_modified))
            ]
        return search_index_updates

    def _init_if_modified_or_created(self, path, status_list) -> tuple:
        """Initialize librarian statuses for modified or created ops."""
        total_paths = len(self.task.files_modified) + len(self.task.files_created)
        status_list += [
            ImporterReadComicsStatus(0, total_paths, subtitle=path),
            ImporterAggregateStatus(0, total_paths, subtitle=path),
            ImporterQueryMissingTagsStatus(subtitle=path),
            ImporterQueryComicUpdatesStatus(subtitle=path),
            ImporterQueryTagLinksStatus(subtitle=path),
            ImporterQueryMissingCoversStatus(subtitle=path),
            ImporterCreateTagsStatus(subtitle=path),
            ImporterUpdateTagsStatus(subtitle=path),
        ]
        if self.task.covers_modified:
            status_list += [
                ImporterUpdateCoversStatus(
                    None,
                    len(self.task.covers_modified),
                    subtitle=path,
                )
            ]
        if self.task.covers_created:
            status_list += [
                ImporterCreateCoversStatus(
                    None,
                    len(self.task.covers_created),
                    subtitle=path,
                )
            ]
        if self.task.files_created or self.task.covers_created:
            status_list += [
                ImporterCreateComicsStatus(
                    None,
                    len(self.task.files_created),
                    subtitle=path,
                )
            ]
        if self.task.files_modified:
            status_list += [
                ImporterUpdateComicsStatus(
                    None,
                    len(self.task.files_modified),
                    subtitle=path,
                )
            ]
        if self.task.files_modified or self.task.files_created:
            # Pre-register the cover-create status (CCC, owned by the
            # cover thread) here so it gets a ``preactive`` timestamp
            # between the comic-create/update phases and link-tags.
            # Otherwise the cover thread's ``start()`` is the row's
            # first appearance — fine for position (NULL preactive
            # sorts above non-null) but means the spinner pops in
            # cold without the "queued" indicator.
            status_list += [
                CreateCoversStatus(),
                ImporterLinkTagsStatus(subtitle=path),
            ]

        num_covers_linked = (
            len(self.task.covers_moved)
            + len(self.task.covers_modified)
            + len(self.task.covers_created)
        )
        if num_covers_linked:
            status_list += [
                ImporterLinkCoversStatus(
                    None,
                    num_covers_linked,
                    subtitle=path,
                )
            ]

        modified = len(self.task.files_moved) + len(self.task.files_modified)
        created = len(self.task.files_created)

        return modified, created

    def _init_librarian_status_deleted(self, status_list) -> int:
        """Init deleted statuses."""
        search_index_updates = 0
        if self.task.files_deleted:
            status_list += [
                ImporterRemoveComicsStatus(None, len(self.task.files_deleted))
            ]
            search_index_updates += len(self.task.files_deleted)
        if self.task.dirs_deleted:
            status_list += [
                ImporterRemoveFoldersStatus(None, len(self.task.dirs_deleted))
            ]
        if self.task.covers_deleted:
            status_list += [
                ImporterRemoveCoversStatus(None, len(self.task.covers_deleted))
            ]
        return search_index_updates

    @staticmethod
    def _init_librarian_status_search_index(
        comic_updates, comic_creates, comic_deletes, status_list
    ) -> None:
        """Init search index statuses."""
        status_list += [
            SearchIndexCleanStatus(total=comic_deletes),
            ImporterFTSUpdateStatus(total=comic_updates),
            ImporterFTSCreateStatus(total=comic_creates),
        ]

    def _init_librarian_status(self, path) -> None:
        """Update the librarian status self.tasks."""
        status_list = []
        moved = self._init_librarian_status_moved(status_list)
        modified, created = self._init_if_modified_or_created(path, status_list)
        deleted = self._init_librarian_status_deleted(status_list)
        status_list += [UpdateGroupTimestampsStatus()]
        self._init_librarian_status_search_index(
            modified + moved,
            created,
            deleted,
            status_list,
        )
        self.status_controller.start_many(status_list)

    def init_apply(self) -> None:
        """Initialize the library and status flags."""
        self.start_time = now()
        self.library.start_update()
        too_long = self._wait_for_filesystem_ops_to_finish()
        if too_long:
            reason = (
                "Import apply waited for the filesystem to stop changing too long. "
                "Try polling again once files have finished copying"
                f" in library: {self.library.path}"
            )
            self.log.warning(reason)
            return
        self._log_task()
        self._init_librarian_status(self.library.path)
