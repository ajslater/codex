"""Bulk import and move comics and folders."""
import logging
from itertools import islice
from pathlib import Path
from time import sleep, time

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.importer.aggregate_metadata import AggregateMetadataMixin
from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.tasks import AdoptOrphanFoldersTask, UpdaterDBDiffTask
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.librarian.notifier.tasks import FAILED_IMPORTS_TASK, LIBRARY_CHANGED_TASK
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexUpdateTask
from codex.librarian.tasks import DelayedTasks
from codex.models import Library
from codex.settings.settings import MAX_IMPORT_BATCH_SIZE

_WRITE_WAIT_EXPIRY = 60


class ComicImporterThread(
    AggregateMetadataMixin,
    DeletedMixin,
    UpdateComicsMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """A worker to handle all bulk database updates."""

    def _wait_for_filesystem_ops_to_finish(self, task: UpdaterDBDiffTask) -> bool:
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
                print(time() - started_checking, "expiry after")
                return True

            old_total_size = total_size
            total_size = 0
            for path_str in all_modified_paths:
                path = Path(path_str)
                if path.exists():
                    total_size += Path(path).stat().st_size
            print(f"{old_total_size=} {total_size=}")
        return False

    def status_op(self, function, library, status):
        """Run a function for a library bracketed by status changes."""
        try:
            self.status_controller.start(status)
            function(library)
        finally:
            self.status_controller.finish(status)

    def batch_db_op(self, library, data, func, status, args=None, updates=False):
        """Run a function batched for memory contrainsts bracketed by status changes."""
        count = 0
        num_elements = len(data)
        if not num_elements:
            return count
        try:
            if updates:
                complete = 0
            else:
                complete = None
            self.status_controller.start(status, complete, num_elements)
            batch_size = min(num_elements, MAX_IMPORT_BATCH_SIZE)
            start = 0
            end = start + batch_size
            is_dict = isinstance(data, dict)
            if not is_dict:
                data = list(data)
            if args is None:
                args = ()

            while start < num_elements:
                if is_dict:
                    batch = dict(islice(data.items(), start, end))  # type: ignore
                else:
                    batch = set(data[start:end])
                all_args = (library, batch, *args)
                count += int(func(*all_args))
                start = end + 1
                end = start + batch_size
        finally:
            self.status_controller.finish(status)

        return count

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

    def _bulk_fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        is_new_failed_imports = 0
        try:
            self.batch_db_op(
                library,
                failed_imports,
                self.bulk_update_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_MODIFIED,
            )

            is_new_failed_imports = self.batch_db_op(
                library,
                failed_imports,
                self.bulk_create_failed_imports,
                ImportStatusTypes.CREATE_FAILED_IMPORTS,
            )

            self.status_op(
                self.bulk_cleanup_failed_imports,
                library,
                ImportStatusTypes.CLEAN_FAILED_IMPORTS,
            )
        except Exception as exc:
            self.log.exception(exc)
        return is_new_failed_imports

    def _bulk_import_comics(
        self, library, create_paths, update_paths, all_bulk_mds, all_m2m_mds
    ):
        """Bulk import comics."""
        # TODO move to big function for refactor
        update_count = create_count = 0
        # all bulk comic mds are keyed on comic paths so can separate them there.

        update_count = self.batch_db_op(
            library,
            update_paths,
            self.bulk_update_comics,
            ImportStatusTypes.FILES_MODIFIED,
            args=(create_paths, all_bulk_mds),
            updates=True,
        )

        create_count = self.batch_db_op(
            library,
            create_paths,
            self.bulk_create_comics,
            ImportStatusTypes.FILES_CREATED,
            args=(all_bulk_mds,),
            updates=True,
        )

        self.batch_db_op(
            library,
            all_m2m_mds,
            self.bulk_query_and_link_comic_m2m_fields,
            ImportStatusTypes.LINK_M2M_FIELDS,
            updates=True,
        )

        self.log.info(f"Updated {update_count} and created {create_count} comics.")
        total_count = update_count + create_count
        return total_count

    def _batch_modified_and_created(
        self, library, modified_paths, created_paths
    ) -> tuple[int, int, int]:
        """Perform one batch of imports."""
        # TODO maybe move to big function for refactor
        mds, m2m_mds, fks, fis = self.get_aggregate_metadata(
            library, modified_paths | created_paths
        )
        modified_paths -= fis.keys()
        created_paths -= fis.keys()

        changed = self.batch_db_op(
            library,
            fks,
            self._bulk_create_comic_relations,
            ImportStatusTypes.CREATE_FKS,
            updates=True,
        )

        imported_count = self._bulk_import_comics(
            library, created_paths, modified_paths, mds, m2m_mds
        )
        changed |= imported_count > 0

        is_new_failed_imports = self._bulk_fail_imports(library, fis)
        return changed, imported_count, is_new_failed_imports

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

    def _init_librarian_status(self, task, path):
        """Update the librarian status tasks."""
        types_map = {}
        total_changes = 0
        if task.files_moved:
            types_map[ImportStatusTypes.FILES_MOVED] = {
                "complete": 0,
                "total": len(task.files_moved),
            }
            total_changes += len(task.files_moved)
        if task.files_modified or task.files_created:
            total_paths = len(task.files_modified) + len(task.files_created)
            total_changes += total_paths
            types_map[ImportStatusTypes.AGGREGATE_TAGS] = {
                "complete": 0,
                "total": total_paths,
                "name": path,
            }
            types_map[ImportStatusTypes.QUERY_MISSING_FKS] = {}
            types_map[ImportStatusTypes.CREATE_FKS] = {}
            if task.files_modified:
                types_map[ImportStatusTypes.FILES_MODIFIED] = {
                    "complete": 0,
                    "total": len(task.files_modified),
                }
            if task.files_created:
                types_map[ImportStatusTypes.FILES_CREATED] = {
                    "complete": 0,
                    "total": len(task.files_created),
                }
            if task.files_modified or task.files_created:
                types_map[ImportStatusTypes.LINK_M2M_FIELDS] = {}
        if task.files_deleted:
            types_map[ImportStatusTypes.FILES_DELETED] = {
                "complete": 0,
                "total": len(task.files_deleted),
            }
            total_changes += len(task.files_deleted)
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_UPDATE] = {
            "complete": 0,
            "total": total_changes,
        }
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_REMOVE] = {}
        self.status_controller.start_many(types_map)

    def _finish_apply(self, library):
        """Finish all librarian statuses."""
        library.update_in_progress = False
        library.save()
        self.status_controller.finish_many(ImportStatusTypes.values())

    def _apply(self, task):
        """Bulk import comics."""
        start_time = time()
        library = Library.objects.get(pk=task.library_id)
        try:
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

            changed = False
            changed |= self.batch_db_op(
                library,
                task.dirs_moved,
                self.bulk_folders_moved,
                ImportStatusTypes.DIRS_MOVED,
            )
            changed |= self.batch_db_op(
                library,
                task.files_moved,
                self.bulk_comics_moved,
                ImportStatusTypes.FILES_MOVED,
            )
            changed |= self.bulk_comics_moved(library, task.files_moved)
            changed |= self.batch_db_op(
                library,
                task.dirs_modified,
                self.bulk_folders_modified,
                ImportStatusTypes.DIRS_MODIFIED,
            )
            (
                changed_comics,
                imported_count,
                new_failed_imports,
            ) = self._batch_modified_and_created(
                library, task.files_modified, task.files_created
            )
            changed |= changed_comics
            changed |= self.batch_db_op(
                library,
                task.dirs_deleted,
                self.bulk_folders_deleted,
                ImportStatusTypes.DIRS_DELETED,
            )
            changed |= self.batch_db_op(
                library,
                task.files_deleted,
                self.bulk_comics_deleted,
                ImportStatusTypes.FILES_DELETED,
            )
            cache.clear()
        finally:
            self._finish_apply(library)
        # Wait to start the search index update in case more updates are incoming.
        until = time() + 3
        delayed_search_task = DelayedTasks(until, (SearchIndexUpdateTask(False),))
        self.librarian_queue.put(delayed_search_task)

        if changed:
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            self.log.info(f"Updated library {library.path} in {elapsed}.")
            suffix = ""
            if imported_count:
                cps = round(imported_count / elapsed_time, 1)
                suffix = f" at {cps} comics per second."
            self.log.info(f"Imported {imported_count} comics{suffix}.")
        if new_failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_TASK)

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, UpdaterDBDiffTask):
            self._apply(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self.adopt_orphan_folders()
        else:
            self.log.warning(f"Bad task sent to library updater {task}")
