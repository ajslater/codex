"""The main importer class."""

from time import time

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.importer.moved import MovedImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.notifier.tasks import FAILED_IMPORTS_TASK, LIBRARY_CHANGED_TASK
from codex.librarian.search.tasks import SearchIndexUpdateTask
from codex.librarian.tasks import DelayedTasks


class ComicImporter(MovedImporter):
    """Initialize, run and finish a bulk import."""

    ##########
    # FINISH #
    ##########
    def _finish_apply_status(self):
        """Finish all librarian statuses."""
        self.library.update_in_progress = False
        self.library.save()
        self.status_controller.finish_many(ImportStatusTypes.values)

    def _finish_apply(self, new_failed_imports, imported_count):
        """Perform final tasks when the apply is done."""
        if self.changed:
            cache.clear()
            elapsed_time = time() - self.start_time.timestamp()
            elapsed = naturaldelta(elapsed_time)
            log_txt = f"Updated library {self.library.path} in {elapsed}."
            if imported_count:
                cps = round(imported_count / elapsed_time, 1)
                log_txt += (
                    f" Imported {imported_count} comics at {cps} comics per second."
                )
            else:
                log_txt += " No comics to import."
            self.log.info(log_txt)
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)

            # Wait to start the search index update in case more updates are incoming.
            until = time() + 1
            delayed_search_task = DelayedTasks(until, (SearchIndexUpdateTask(False),))
            self.librarian_queue.put(delayed_search_task)
        else:
            self.log.info("No updates neccissary.")
        if new_failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_TASK)

    def apply(self):
        """Bulk import comics."""
        try:
            self.init_apply()
            self.move_and_modify_dirs()

            #############
            # AGGREGATE #
            #############
            self.get_aggregate_metadata()

            #########
            # QUERY #
            #########
            self.query_all_missing_fks()
            self.query_missing_custom_covers()

            #####################
            # UPDATE AND CREATE #
            #####################
            self.create_all_fks()
            self.update_custom_covers()
            self.create_custom_covers()

            imported_count = self.bulk_update_comics()
            imported_count += self.bulk_create_comics()

            ########
            # LINK #
            ########
            self.bulk_query_and_link_comic_m2m_fields()
            self.link_custom_covers()
            self.changed += imported_count

            new_failed_imports = self.fail_imports()

            deleted_comic_groups = self.delete()

            self.update_all_groups(deleted_comic_groups, self.start_time)

        finally:
            self._finish_apply_status()

        self._finish_apply(new_failed_imports, imported_count)
