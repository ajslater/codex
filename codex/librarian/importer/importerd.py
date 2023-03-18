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
from codex.models import Comic, Credit, Library
from codex.settings.settings import MAX_IMPORT_BATCH_SIZE

_WRITE_WAIT_EXPIRY = 60
_CREDIT_FK_NAMES = ("role", "person")


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

    def _init_librarian_status(self, task, path):
        """Update the librarian status tasks."""
        types_map = {}
        search_index_updates = 0
        if task.dirs_moved:
            types_map[ImportStatusTypes.DIRS_MOVED] = {
                "complete": 0,
                "total": len(task.dirs_moved),
            }
        if task.files_moved:
            types_map[ImportStatusTypes.FILES_MOVED] = {
                "complete": 0,
                "total": len(task.files_moved),
            }
            search_index_updates += len(task.files_moved)
        if task.files_modified:
            types_map[ImportStatusTypes.DIRS_MODIFIED] = {
                "complete": 0,
                "total": len(task.dirs_modified),
            }
        if task.files_modified or task.files_created:
            total_paths = len(task.files_modified) + len(task.files_created)
            search_index_updates += total_paths
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
            search_index_updates += len(task.files_deleted)
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_UPDATE] = {
            "complete": 0,
            "total": search_index_updates,
        }
        types_map[SearchIndexStatusTypes.SEARCH_INDEX_REMOVE] = {}
        self.status_controller.start_many(types_map)

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

    def batch_db_op(
        self, library, data, func, status, args=None, updates=True, count=0, total=0
    ):
        """Run a function batched for memory contrainsts bracketed by status changes."""
        num_elements = len(data)
        finish = bool(total)
        try:
            if not num_elements:
                return count
            if updates:
                complete = count
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

            if not total:
                total = num_elements
            while start < num_elements:
                if updates:
                    self.status_controller.update(status, count, num_elements)
                if is_dict:
                    batch = dict(islice(data.items(), start, end))  # type: ignore
                else:
                    batch = set(data[start:end])
                all_args = (library, batch, count, total, *args)
                count += int(func(*all_args))
                start = end + 1
                end = start + batch_size
        finally:
            if finish:
                self.status_controller.finish(status)

        return count

    def _move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = self.batch_db_op(
            library,
            task.dirs_moved,
            self.bulk_folders_moved,
            ImportStatusTypes.DIRS_MOVED,
        )
        task.dirs_moved = None
        changed += self.batch_db_op(
            library,
            task.files_moved,
            self.bulk_comics_moved,
            ImportStatusTypes.FILES_MOVED,
        )
        task.files_moved = None
        changed += self.batch_db_op(
            library,
            task.dirs_modified,
            self.bulk_folders_modified,
            ImportStatusTypes.DIRS_MODIFIED,
        )
        task.dirs_modified = None
        return changed

    @staticmethod
    def _get_query_fks_totals(fks):
        """Get the query foreign keys totals."""
        fks_total = 0
        for key, objs in fks.items():
            if key == "group_trees":
                for trees in objs.values():
                    fks_total += len(trees)
            else:
                fks_total += len(objs)
        return fks_total

    def query_all_missing_fks(self, library, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_credits = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        try:
            self.log.debug(
                f"Querying existing foreign keys for comics in {library.path}"
            )
            count = 0
            fks_total = self._get_query_fks_totals(fks)
            self.status_controller.start(
                ImportStatusTypes.QUERY_MISSING_FKS, 0, fks_total
            )

            if "credits" in fks:
                count += self.batch_db_op(
                    library,
                    fks.pop("credits"),
                    self.query_missing_credits,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_credits,),
                    count=count,
                    total=fks_total,
                )
                self.log.info(f"Prepared {len(create_credits)} new credits.")

            if "group_trees" in fks:
                for group_class, groups in fks.pop("group_trees").items():
                    count += self.batch_db_op(
                        library,
                        groups,
                        self.query_missing_group_type,
                        ImportStatusTypes.QUERY_MISSING_FKS,
                        args=(group_class, create_groups, update_groups),
                        count=count,
                        total=fks_total,
                    )
                self.log.info(f"Prepared {len(create_groups)} new groups.")

            if "comic_paths" in fks:
                count += self.batch_db_op(
                    library,
                    fks.pop("comic_paths"),
                    self.query_missing_folder_paths,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_folder_paths,),
                    count=count,
                    total=fks_total,
                )
                self.log.info(f"Prepared {len(create_folder_paths)} new folders.")

            for fk_field in tuple(fks.keys()):
                names = fks.pop(fk_field)
                if fk_field in _CREDIT_FK_NAMES:
                    base_cls = Credit
                else:
                    base_cls = Comic
                count += self.batch_db_op(
                    library,
                    names,
                    self.query_missing_simple_models,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_fks, base_cls, fk_field, "name"),
                    count=count,
                    total=fks_total,
                )
                if num_names := len(names):
                    self.log.info(f"Prepared {num_names} new {fk_field}.")
        finally:
            self.status_controller.finish(ImportStatusTypes.QUERY_MISSING_FKS)

        return (
            create_fks,
            create_groups,
            update_groups,
            create_folder_paths,
            create_credits,
        )

    @staticmethod
    def _get_create_fks_totals(
        create_groups, update_groups, create_folder_paths, create_fks, create_credits
    ):
        total_fks = 0
        for groups in create_groups.values():
            total_fks += len(groups)
        for groups in update_groups.values():
            total_fks += len(groups)
        total_fks += len(create_folder_paths)
        for names in create_fks.values():
            total_fks += len(names)
        total_fks += len(create_credits)
        return total_fks

    def bulk_create_all_fks(
        self,
        library,
        create_fks,
        create_groups,
        update_groups,
        create_folder_paths,
        create_credits,
    ):
        """Bulk create all foreign keys."""
        try:
            count = 0
            total_fks = self._get_create_fks_totals(
                create_groups,
                update_groups,
                create_folder_paths,
                create_fks,
                create_credits,
            )
            status = ImportStatusTypes.CREATE_FKS
            self.status_controller.start(status, 0, total_fks)

            self.log.debug(f"Creating comic foreign keys for {library.path}...")

            self.log.debug(f"Preparing {len(create_groups)} groups for creation..")
            for group_class, group_tree_counts in create_groups.items():
                count += self.batch_db_op(
                    library,
                    group_tree_counts,
                    self.bulk_group_creator,
                    status,
                    args=(group_class,),
                    count=count,
                    total=total_fks,
                )

            self.log.debug(f"Preparing {len(update_groups)} groups for update...")
            for group_class, group_tree_counts in update_groups.items():
                count += self.batch_db_op(
                    library,
                    group_tree_counts,
                    self.bulk_group_updater,
                    status,
                    args=(group_class,),
                    count=count,
                    total=total_fks,
                )

            count += self.batch_db_op(
                library,
                create_folder_paths,
                self.bulk_folders_create,
                status,
                count=count,
                total=total_fks,
            )

            for named_cls, names in create_fks.items():
                count += self.batch_db_op(
                    library,
                    names,
                    self.bulk_create_named_models,
                    status,
                    args=(named_cls,),
                    count=count,
                    total=total_fks,
                )

            # This must happen after credit_fks created by create_named_models
            count += self.batch_db_op(
                library,
                create_credits,
                self.bulk_create_credits,
                status,
                count=count,
                total=total_fks,
            )
            return count
        finally:
            self.status_controller.finish(ImportStatusTypes.CREATE_FKS)

    def _create_comic_relations(self, library, fks):
        """Query all foreign keys to determine what needs creating, then create them."""
        if not fks:
            return 0

        (
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        ) = self.query_all_missing_fks(library, fks)

        count = self.bulk_create_all_fks(
            library,
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        )
        return count

    def _update_create_and_link_comics(
        self, library, modified_paths, created_paths, mds, m2m_mds
    ):
        """Update, create and link comics."""
        update_count = create_count = 0

        update_count = self.batch_db_op(
            library,
            modified_paths,
            self.bulk_update_comics,
            ImportStatusTypes.FILES_MODIFIED,
            args=(created_paths, mds),
        )

        create_count = self.batch_db_op(
            library,
            created_paths,
            self.bulk_create_comics,
            ImportStatusTypes.FILES_CREATED,
            args=(mds,),
        )

        linked_count = self.batch_db_op(
            library,
            m2m_mds,
            self.bulk_query_and_link_comic_m2m_fields,
            ImportStatusTypes.LINK_M2M_FIELDS,
        )
        if linked_count:
            self.log.info(f"Linked {linked_count} comics to tags.")

        imported_count = update_count + create_count
        if imported_count:
            self.log.info(f"Updated {update_count} and created {create_count} comics.")
        return imported_count

    def _bulk_fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        is_new_failed_imports = 0
        try:
            update_fis = {}
            create_fis = {}
            delete_fi_paths = set()
            self.batch_db_op(
                library,
                failed_imports,
                self.query_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_QUERY,
                args=(update_fis, create_fis, delete_fi_paths),
            )

            self.batch_db_op(
                library,
                update_fis,
                self.bulk_update_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_MODIFIED,
            )

            is_new_failed_imports = self.batch_db_op(
                library,
                create_fis,
                self.bulk_create_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_CREATE,
            )

            self.batch_db_op(
                library,
                delete_fi_paths,
                self.bulk_cleanup_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_CLEAN,
            )
        except Exception as exc:
            self.log.exception(exc)
        return is_new_failed_imports

    def _delete(self, library, task):
        """Delete files and folders."""
        changed = self.batch_db_op(
            library,
            task.dirs_deleted,
            self.bulk_folders_deleted,
            ImportStatusTypes.DIRS_DELETED,
        )
        task.dirs_deleted = None
        changed += self.batch_db_op(
            library,
            task.files_deleted,
            self.bulk_comics_deleted,
            ImportStatusTypes.FILES_DELETED,
        )
        task.files_deleted = None
        return changed

    def _finish_apply_status(self, library):
        """Finish all librarian statuses."""
        library.update_in_progress = False
        library.save()
        self.status_controller.finish_many(ImportStatusTypes.values())

    def _finish_apply(
        self, library, changed, start_time, imported_count, new_failed_imports
    ):
        """Perform final tasks when the apply is done."""
        if changed:
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            log_txt = f"Updated library {library.path} in {elapsed}."
            if imported_count:
                cps = round(imported_count / elapsed_time, 1)
                log_txt += (
                    f" Imported {imported_count} comics" f" at {cps} comics per second."
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
        library = Library.objects.get(pk=task.library_id)
        try:
            self._init_apply(library, task)

            changed = 0
            changed += self._move_and_modify_dirs(library, task)

            modified_paths = task.files_modified
            created_paths = task.files_created
            task.files_modified = task.files_created = None
            mds, m2m_mds, fks, fis = self.get_aggregate_metadata(
                library, modified_paths | created_paths
            )
            modified_paths -= fis.keys()
            created_paths -= fis.keys()

            changed += self._create_comic_relations(library, fks)

            imported_count = self._update_create_and_link_comics(
                library, modified_paths, created_paths, mds, m2m_mds
            )
            changed += imported_count
            modified_paths = created_paths = mds = m2m_mds = None

            new_failed_imports = self._bulk_fail_imports(library, fis)

            changed += self._delete(library, task)
            cache.clear()
        finally:
            self._finish_apply_status(library)

        self._finish_apply(
            library, changed, start_time, imported_count, new_failed_imports
        )

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, UpdaterDBDiffTask):
            self._apply(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self.adopt_orphan_folders()
        else:
            self.log.warning(f"Bad task sent to library updater {task}")
