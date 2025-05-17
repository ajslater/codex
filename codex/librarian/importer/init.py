"""Initiale Importer."""

from multiprocessing.queues import Queue
from pathlib import Path
from time import sleep, time
from typing import Any

from django.utils.timezone import now

from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.tasks import ImportDBDiffTask
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexAbortTask
from codex.librarian.status import Status
from codex.librarian.worker import WorkerStatusMixin
from codex.models import Library
from codex.settings import LOGLEVEL

_WRITE_WAIT_EXPIRY = 60


class InitImporter(WorkerStatusMixin):
    """Initial Importer."""

    def __init__(self, task: ImportDBDiffTask, logger_, librarian_queue: Queue):
        """Initialize the import."""
        self.init_worker(logger_, librarian_queue)
        self.task: ImportDBDiffTask = task
        self.metadata: dict[str, Any] = {}
        self.changed: int = 0
        self.library = Library.objects.only("path", "update_in_progress").get(
            pk=self.task.library_id
        )
        self.start_time = now()
        self._is_log_debug_task = (
            self.log.level(LOGLEVEL).no <= self.log.level("DEBUG").no
        )

    def _wait_for_filesystem_ops_to_finish(self) -> bool:
        """Watchdog sends events before filesystem events finish, so wait for them."""
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
                    total_size += Path(path).stat().st_size
        return False

    #######
    # LOG #
    #######
    def _log_task_construct_dirs_log(self):
        """Construct dirs log line."""
        dirs_log = []
        if self.task.dirs_moved:
            dirs_log += [f"{len(self.task.dirs_moved)} moved"]
        if self.task.dirs_modified:
            dirs_log += [f"{len(self.task.dirs_modified)} modified"]
        if self.task.dirs_deleted:
            dirs_log += [f"{len(self.task.dirs_deleted)} deleted"]
        return dirs_log

    def _log_task_construct_comics_log(self):
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

    def _log_task(self):
        """Log the watchdog event self.task."""
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
    def _init_librarian_status_moved(self, status_list):
        """Initialize moved statuses."""
        search_index_updates = 0
        if self.task.dirs_moved:
            status_list += [
                Status(ImportStatusTypes.MOVE_FOLDERS, None, len(self.task.dirs_moved))
            ]
        if self.task.files_moved:
            status_list += [
                Status(ImportStatusTypes.MOVE_COMICS, None, len(self.task.files_moved))
            ]
            search_index_updates += len(self.task.files_moved)
        if self.task.covers_moved:
            status_list += [
                Status(
                    ImportStatusTypes.MOVE_CUSTOM_COVERS,
                    None,
                    len(self.task.covers_moved),
                )
            ]
        if self.task.dirs_modified:
            status_list += [
                Status(
                    ImportStatusTypes.UPDATE_FOLDERS, None, len(self.task.dirs_modified)
                )
            ]
        return search_index_updates

    def _init_if_modified_or_created(self, path, status_list):
        """Initialize librarian statuses for modified or created ops."""
        total_paths = len(self.task.files_modified) + len(self.task.files_created)
        status_list += [
            Status(ImportStatusTypes.READ_TAGS, 0, total_paths, subtitle=path),
            Status(ImportStatusTypes.AGGREGATE_TAGS, 0, total_paths, subtitle=path),
            Status(ImportStatusTypes.QUERY_MISSING_TAGS, subtitle=path),
            Status(ImportStatusTypes.QUERY_MISSING_COVERS, subtitle=path),
            Status(ImportStatusTypes.CREATE_TAGS, subtitle=path),
        ]
        if self.task.files_modified:
            status_list += [
                Status(
                    ImportStatusTypes.UPDATE_COMICS,
                    None,
                    len(self.task.files_modified),
                    subtitle=path,
                )
            ]
        if self.task.covers_modified:
            status_list += [
                Status(
                    ImportStatusTypes.UPDATE_CUSTOM_COVERS,
                    None,
                    len(self.task.covers_modified),
                    subtitle=path,
                )
            ]

        if self.task.files_created or self.task.covers_created:
            status_list += [
                Status(
                    ImportStatusTypes.CREATE_COMICS,
                    None,
                    len(self.task.files_created),
                    subtitle=path,
                )
            ]
        if self.task.covers_created:
            status_list += [
                Status(
                    ImportStatusTypes.CREATE_CUSTOM_COVERS,
                    None,
                    len(self.task.covers_created),
                    subtitle=path,
                )
            ]

        if self.task.files_modified or self.task.files_created:
            status_list += [
                Status(ImportStatusTypes.LINK_COMICS_TO_TAGS, subtitle=path)
            ]

        num_covers_linked = (
            len(self.task.covers_moved)
            + len(self.task.covers_modified)
            + len(self.task.covers_created)
        )
        if num_covers_linked:
            status_list += [
                Status(
                    ImportStatusTypes.LINK_CUSTOM_COVERS,
                    None,
                    num_covers_linked,
                    subtitle=path,
                )
            ]

        return total_paths

    def _init_librarian_status_deleted(self, status_list):
        """Init deleted statuses."""
        search_index_updates = 0
        if self.task.files_deleted:
            status_list += [
                Status(
                    ImportStatusTypes.REMOVE_COMICS, None, len(self.task.files_deleted)
                )
            ]
            search_index_updates += len(self.task.files_deleted)
        if self.task.covers_deleted:
            status_list += [
                Status(
                    ImportStatusTypes.REMOVE_CUSTOM_COVERS,
                    None,
                    len(self.task.covers_deleted),
                )
            ]
        return search_index_updates

    @staticmethod
    def _init_librarian_status_search_index(search_index_updates, status_list):
        """Init search index statuses."""
        status_list += [
            Status(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
                total=search_index_updates,
            ),
            Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE),
        ]

    def _init_librarian_status(self, path):
        """Update the librarian status self.tasks."""
        status_list = []
        search_index_updates = 0
        search_index_updates += self._init_librarian_status_moved(status_list)
        if (
            self.task.files_modified
            or self.task.files_created
            or self.task.covers_modified
            or self.task.covers_created
        ):
            search_index_updates += self._init_if_modified_or_created(path, status_list)
        search_index_updates += self._init_librarian_status_deleted(status_list)
        status_list += [Status(ImportStatusTypes.UPDATE_GROUP_TIMESTAMPS)]
        self._init_librarian_status_search_index(search_index_updates, status_list)
        self.status_controller.start_many(status_list)

    def init_apply(self):
        """Initialize the library and status flags."""
        self.start_time = now()
        self.librarian_queue.put(SearchIndexAbortTask())
        self.library.update_in_progress = True
        self.library.save()
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
