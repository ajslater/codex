"""Bulk import and move comics and folders."""
import logging
import time

from datetime import datetime
from pathlib import Path

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.db.aggregate_metadata import AggregateMetadataMixin
from codex.librarian.db.deleted import DeletedMixin
from codex.librarian.db.failed_imports import FailedImportsMixin
from codex.librarian.db.moved import MovedMixin
from codex.librarian.db.status import ImportStatusTypes
from codex.librarian.db.tasks import AdoptOrphanFoldersTask, UpdaterDBDiffTask
from codex.librarian.queue_mp import DelayedTasks
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexUpdateTask
from codex.librarian.status_control import StatusControl
from codex.models import Library
from codex.notifier.tasks import FAILED_IMPORTS_TASK, LIBRARY_CHANGED_TASK


_WRITE_WAIT_EXPIRY = 5


class Updater(
    AggregateMetadataMixin,
    DeletedMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """A worker to handle all bulk database updates."""

    NAME = "Updater"  # type: ignore

    def _wait_for_filesystem_ops_to_finish(self, task: UpdaterDBDiffTask) -> bool:
        """Watchdog sends events before filesystem events finish, so wait for them."""
        started_checking = time.time()

        # Don't wait for deletes to complete.
        # Do wait for move, modified, create files before import.
        all_modified_paths = (
            frozenset(task.dirs_moved.values())
            | frozenset(task.files_moved.values())
            | task.dirs_modified
            | task.files_modified
            | task.files_created
        )

        old_total_size = -1
        total_size = 0
        wait_time = 2
        while old_total_size != total_size:
            if old_total_size > 0:
                # second time around or more
                time.sleep(wait_time)
                wait_time = wait_time**2
                self.logger.debug(
                    f"Waiting for files to copy before import: "
                    f"{old_total_size} != {total_size}"
                )
            if time.time() - started_checking > _WRITE_WAIT_EXPIRY:
                return True

            old_total_size = total_size
            total_size = 0
            for path_str in all_modified_paths:
                path = Path(path_str)
                if path.exists():
                    total_size += Path(path).stat().st_size
        return False

    def _bulk_create_comic_relations(self, library, fks) -> bool:
        """Query all foreign keys to determine what needs creating, then create them."""
        if not fks:
            return False

        (
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        ) = self.query_all_missing_fks(library.path, fks)

        changed = self.bulk_create_all_fks(
            library,
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        )
        return changed

    def _batch_modified_and_created(
        self, library, modified_paths, created_paths
    ) -> tuple[bool, int, bool]:
        """Perform one batch of imports."""
        mds, m2m_mds, fks, fis = self.get_aggregate_metadata(
            library, modified_paths | created_paths
        )
        modified_paths -= fis.keys()
        created_paths -= fis.keys()

        changed = self._bulk_create_comic_relations(library, fks)

        imported_count = self.bulk_import_comics(
            library, created_paths, modified_paths, mds, m2m_mds
        )
        new_failed_imports = self.bulk_fail_imports(library, fis)
        changed |= imported_count > 0
        return changed, imported_count, bool(new_failed_imports)

    def _log_task(self, path, task):
        if self.logger.getEffectiveLevel() < logging.DEBUG:
            return
        dirs_log = []
        if task.dirs_moved:
            dirs_log += [f"{len(task.dirs_moved)} moved"]
        if task.dirs_modified:
            dirs_log += [f"{len(task.dirs_modified)} modified"]
        if task.dirs_deleted:
            dirs_log += [f"{len(task.dirs_deleted)} deleted"]
        comics_log = []
        if task.files_moved:
            comics_log += [f"{len(task.files_moved)} moved"]
        if task.files_modified:
            comics_log += [f"{len(task.files_modified)} modified"]
        if task.files_created:
            comics_log += [f"{len(task.files_created)} created"]
        if task.files_deleted:
            comics_log += [f"{len(task.files_deleted)} deleted"]

        self.logger.debug(f"Updating library {path}...")
        if comics_log:
            log = "Comics: "
            log += ", ".join(comics_log)
            self.logger.debug("  " + log)
        if dirs_log:
            log = "Folders: "
            log += ", ".join(dirs_log)
            self.logger.debug("  " + log)

    def _init_librarian_status(self, task, path):
        """Update the librarian status tasks."""
        types_map = {}
        total_changes = 0
        if task.files_moved:
            types_map[ImportStatusTypes.FILES_MOVED] = {"total": len(task.files_moved)}
            total_changes += len(task.files_moved)
        if task.files_modified or task.files_created:
            total_paths = len(task.files_modified) + len(task.files_created)
            total_changes += total_paths
            types_map[ImportStatusTypes.AGGREGATE_TAGS] = {
                "total": total_paths,
                "name": path,
            }
            types_map[ImportStatusTypes.QUERY_MISSING_FKS] = {}
            types_map[ImportStatusTypes.CREATE_FKS] = {}
            if task.files_modified:
                types_map[ImportStatusTypes.FILES_MODIFIED] = {
                    "name": f"({len(task.files_modified)})"
                }
            if task.files_created:
                types_map[ImportStatusTypes.FILES_CREATED] = {
                    "name": f"({len(task.files_created)})"
                }
            if task.files_modified or task.files_created:
                types_map[ImportStatusTypes.LINK_M2M_FIELDS] = {}
        if task.files_deleted:
            types_map[ImportStatusTypes.FILES_DELETED] = {
                "name": f"({len(task.files_deleted)})"
            }
            total_changes += len(task.files.deleted)
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_PREPARE] = {
            "total": total_changes
        }
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_COMMIT] = {
            "name": f"({total_changes})"
        }
        StatusControl.start_many(types_map)

    def _finish_apply(self, library):
        """Finish all librarian statuses."""
        library.update_in_progress = False
        library.save()
        StatusControl.finish_many(ImportStatusTypes.values())

    def _apply(self, task):
        """Bulk import comics."""
        start_time = datetime.now()
        library = Library.objects.get(pk=task.library_id)
        try:
            library.update_in_progress = True
            library.save()
            too_long = self._wait_for_filesystem_ops_to_finish(task)
            if too_long:
                self.logger.warning(
                    "Import apply waited for the filesystem to stop changing too long. "
                    "Try polling again once files have finished copying."
                )
                return
            self._log_task(library.path, task)
            self._init_librarian_status(task, library.path)

            changed = False
            changed |= self.bulk_folders_moved(library, task.dirs_moved)
            changed |= self.bulk_comics_moved(library, task.files_moved)
            changed |= self.bulk_folders_modified(library, task.dirs_modified)
            (
                changed_comics,
                imported_count,
                new_failed_imports,
            ) = self._batch_modified_and_created(
                library, task.files_modified, task.files_created
            )
            changed |= changed_comics
            changed |= self.bulk_folders_deleted(library, task.dirs_deleted)
            changed |= self.bulk_comics_deleted(library, task.files_deleted)
            cache.clear()
        finally:
            self._finish_apply(library)
        # Wait to start the search index update in case more updates are incoming.
        delayed_search_task = DelayedTasks(2, (SearchIndexUpdateTask(False),))
        self.librarian_queue.put(delayed_search_task)

        if changed:
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)
            elapsed_time = datetime.now() - start_time
            elapsed = naturaldelta(elapsed_time)
            self.logger.info(f"Updated library {library.path} in {elapsed}.")
            suffix = ""
            if imported_count:
                cps = int(imported_count / elapsed_time.total_seconds())
                suffix = f" at {cps} comics per second."
            self.logger.info(f"Imported {imported_count} comics{suffix}.")
        if new_failed_imports:
            self.librarian_queue.put(
                FAILED_IMPORTS_TASK
            )  # TODO does this trigger a refresh like CHANGED?

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, UpdaterDBDiffTask):
            self._apply(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self.adopt_orphan_folders()
        else:
            self.logger.warning(f"Bad task sent to library updater {task}")
