"""Bulk import and move comics and folders."""

import logging
from pathlib import Path
from time import sleep, time

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.importer.aggregate_metadata import AggregateMetadataMixin
from codex.librarian.importer.const import FIS, FKS, M2M_MDS, MDS
from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.tasks import AdoptOrphanFoldersTask, ImportDBDiffTask
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.librarian.notifier.tasks import FAILED_IMPORTS_TASK, LIBRARY_CHANGED_TASK
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexAbortTask, SearchIndexUpdateTask
from codex.librarian.tasks import DelayedTasks
from codex.models import Library
from codex.status import Status

_WRITE_WAIT_EXPIRY = 60


class ComicImporterThread(
    AggregateMetadataMixin,
    DeletedMixin,
    UpdateComicsMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """A worker to handle all bulk database updates."""

    def _wait_for_filesystem_ops_to_finish(self, task: ImportDBDiffTask) -> bool:
        """Watchdog sends events before filesystem events finish, so wait for them."""
        started_checking = time()

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
                sleep(wait_time)
                wait_time = wait_time**2
                self.log.debug(
                    f"Waiting for files to copy before import: "
                    f"{old_total_size} != {total_size}"
                )
            if time() - started_checking > _WRITE_WAIT_EXPIRY:
                return True

            old_total_size = total_size
            total_size = 0
            for path_str in all_modified_paths:
                path = Path(path_str)
                if path.exists():
                    total_size += Path(path).stat().st_size
        return False

    def _log_task_construct_dirs_log(self, task):
        """Construct dirs log line."""
        dirs_log = []
        if task.dirs_moved:
            dirs_log += [f"{len(task.dirs_moved)} moved"]
        if task.dirs_modified:
            dirs_log += [f"{len(task.dirs_modified)} modified"]
        if task.dirs_deleted:
            dirs_log += [f"{len(task.dirs_deleted)} deleted"]
        return dirs_log

    def _log_task_construct_comics_log(self, task):
        """Construct comcis log line."""
        comics_log = []
        if task.files_moved:
            comics_log += [f"{len(task.files_moved)} moved"]
        if task.files_modified:
            comics_log += [f"{len(task.files_modified)} modified"]
        if task.files_created:
            comics_log += [f"{len(task.files_created)} created"]
        if task.files_deleted:
            comics_log += [f"{len(task.files_deleted)} deleted"]
        return comics_log

    def _log_task(self, path, task):
        """Log the watchdog event task."""
        if self.log.getEffectiveLevel() < logging.DEBUG:
            return

        self.log.debug(f"Updating library {path}...")
        comics_log = self._log_task_construct_comics_log(task)
        if comics_log:
            log = "Comics: "
            log += ", ".join(comics_log)
            self.log.debug("  " + log)

        dirs_log = self._log_task_construct_dirs_log(task)
        if dirs_log:
            log = "Folders: "
            log += ", ".join(dirs_log)
            self.log.debug("  " + log)

    @staticmethod
    def _init_if_modified_or_created(task, path, status_list):
        """Initialize librarian statuses for modified or created ops."""
        total_paths = len(task.files_modified) + len(task.files_created)
        status_list += [
            Status(ImportStatusTypes.AGGREGATE_TAGS, 0, total_paths, subtitle=path),
            Status(ImportStatusTypes.QUERY_MISSING_FKS),
            Status(ImportStatusTypes.CREATE_FKS),
        ]
        if task.files_modified:
            status_list += [
                Status(
                    ImportStatusTypes.FILES_MODIFIED,
                    None,
                    len(task.files_modified),
                )
            ]
        if task.files_created:
            status_list += [
                Status(ImportStatusTypes.FILES_CREATED, None, len(task.files_created))
            ]
        if task.files_modified or task.files_created:
            status_list += [Status(ImportStatusTypes.LINK_M2M_FIELDS)]
        return total_paths

    def _init_librarian_status(self, task, path):
        """Update the librarian status tasks."""
        status_list = []
        search_index_updates = 0
        if task.dirs_moved:
            status_list += [
                Status(ImportStatusTypes.DIRS_MOVED, None, len(task.dirs_moved))
            ]
        if task.files_moved:
            status_list += [
                Status(ImportStatusTypes.FILES_MOVED, None, len(task.files_moved))
            ]
            search_index_updates += len(task.files_moved)
        if task.files_modified:
            status_list += [
                Status(ImportStatusTypes.DIRS_MODIFIED, None, len(task.dirs_modified))
            ]
        if task.files_modified or task.files_created:
            search_index_updates += self._init_if_modified_or_created(
                task, path, status_list
            )
        if task.files_deleted:
            status_list += [
                Status(ImportStatusTypes.FILES_DELETED, None, len(task.files_deleted))
            ]
            search_index_updates += len(task.files_deleted)
        status_list += [
            Status(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
                0,
                search_index_updates,
            ),
            Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE),
        ]
        self.status_controller.start_many(status_list)

    def _init_apply(self, library, task):
        """Initialize the library and status flags."""
        library.update_in_progress = True
        library.save()
        too_long = self._wait_for_filesystem_ops_to_finish(task)
        if too_long:
            self.log.warning(
                "Import apply waited for the filesystem to stop changing too long. "
                "Try polling again once files have finished copying"
                f" in library: {library.path}"
            )
            return
        self._log_task(library.path, task)
        self._init_librarian_status(task, library.path)

    def _create_comic_relations(self, library, fks):
        """Query all foreign keys to determine what needs creating, then create them."""
        if not fks:
            return 0
        create_data = self.query_all_missing_fks(library.path, fks)
        return self.create_all_fks(library, create_data)

    def _finish_apply_status(self, library):
        """Finish all librarian statuses."""
        library.update_in_progress = False
        library.save()
        self.status_controller.finish_many(ImportStatusTypes.values)

    def _finish_apply(self, changed, new_failed_imports, changed_args):
        """Perform final tasks when the apply is done."""
        if changed:
            library, start_time, imported_count = changed_args
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            log_txt = f"Updated library {library.path} in {elapsed}."
            if imported_count:
                cps = round(imported_count / elapsed_time, 1)
                log_txt += (
                    f" Imported {imported_count} comics at {cps} comics per second."
                )
            else:
                log_txt += " No comics to import."
            self.log.info(log_txt)

            # Wait to start the search index update in case more updates are incoming.
            until = time() + 3
            delayed_search_task = DelayedTasks(until, (SearchIndexUpdateTask(False),))
            self.librarian_queue.put(delayed_search_task)
        else:
            self.log.info("No updates neccissary.")
        if new_failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_TASK)

    def _apply(self, task):
        """Bulk import comics."""
        start_time = time()
        self.librarian_queue.put(SearchIndexAbortTask())
        library = Library.objects.get(pk=task.library_id)
        try:
            self._init_apply(library, task)

            changed = 0
            changed += self.move_and_modify_dirs(library, task)

            modified_paths = task.files_modified
            created_paths = task.files_created
            task.files_modified = task.files_created = None
            mds = {}
            m2m_mds = {}
            fks = {}
            fis = {}
            all_metadata = {
                MDS: mds,
                M2M_MDS: m2m_mds,
                FKS: fks,
                FIS: fis,
            }
            self.get_aggregate_metadata(
                modified_paths | created_paths, library.path, all_metadata
            )
            all_metadata = None
            modified_paths -= fis.keys()
            created_paths -= fis.keys()

            changed += self._create_comic_relations(library, fks)
            fks = None

            imported_count = self.bulk_update_comics(
                modified_paths,
                library,
                created_paths,
                mds,
            )
            modified_paths = None
            imported_count += self.bulk_create_comics(created_paths, library, mds)
            created_paths = mds = None
            self.bulk_query_and_link_comic_m2m_fields(m2m_mds)
            m2m_mds = None
            changed += imported_count

            new_failed_imports = self.fail_imports(
                library, fis, bool(task.files_deleted)
            )

            changed += self.delete(library, task)
            cache.clear()
        finally:
            self._finish_apply_status(library)

        changed_args = (library, start_time, imported_count)
        self._finish_apply(changed, new_failed_imports, changed_args)

    def process_item(self, item):
        """Run the updater."""
        task = item
        if isinstance(task, ImportDBDiffTask):
            self._apply(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self.adopt_orphan_folders()
        else:
            self.log.warning(f"Bad task sent to library updater {task}")
