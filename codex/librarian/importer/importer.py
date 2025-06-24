"""The main importer class."""

from dataclasses import dataclass
from time import time

from django.core.cache import cache
from humanize import naturaldelta

from codex.librarian.importer.moved import MovedImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.notifier.tasks import (
    FAILED_IMPORTS_CHANGED_TASK,
    LIBRARY_CHANGED_TASK,
)
from codex.librarian.search.tasks import SearchIndexUpdateTask
from codex.librarian.tasks import DelayedTasks


@dataclass
class Counts:
    """Total counts of operations."""

    comic = 0
    fk = 0
    link = 0
    deleted = 0


class ComicImporter(MovedImporter):
    """Initialize, run and finish a bulk import."""

    def _finish_apply(
        self,
        counts: Counts,
        *,
        new_failed_imports: bool,
    ):
        """Perform final tasks when the apply is done."""
        self.library.end_update()
        self.status_controller.finish_many(ImportStatusTypes.values)
        elapsed_time = time() - self.start_time.timestamp()
        elapsed = naturaldelta(elapsed_time)
        if self.changed or self.covers_changed:
            cache.clear()
            log_txt = f"Updated library {self.library.path} in {elapsed}."
            if counts.comic:
                cps = round(counts.comic / elapsed_time, 1)
                log_txt += f" Imported {counts.comic} at {cps} comics per second."
            else:
                log_txt += " No comics to import."
            if counts.fk:
                log_txt += f" {counts.fk} tags imported."
            if counts.link:
                log_txt += f" {counts.link} tags linked."
            if counts.deleted:
                log_txt += f" {counts.deleted} comics deleted."

            self.librarian_queue.put(LIBRARY_CHANGED_TASK)

            if self.changed:
                # Wait to start the search index update in case more updates are incoming.
                until = time() + 2
                delayed_search_task = DelayedTasks(
                    until, (SearchIndexUpdateTask(rebuild=False),)
                )
                self.librarian_queue.put(delayed_search_task)
        else:
            log_txt = f"No updates neccissary for library {self.library.path}. Finished in {elapsed}."
        self.log.success(log_txt)
        if new_failed_imports:
            self.librarian_queue.put(FAILED_IMPORTS_CHANGED_TASK)

    def apply(self):
        """Bulk import comics."""
        new_failed_imports = False
        count = Counts()
        try:
            self.init_apply()
            self.changed += self.move_and_modify_dirs()

            #############
            # AGGREGATE #
            #############
            self.extract_metadata()
            self.aggregate_metadata()

            #########
            # QUERY #
            #########
            self.query_actions()
            self.query_missing_custom_covers()

            #####################
            # UPDATE AND CREATE #
            #####################
            fk_count = self.create_all_fks()
            fk_count += self.update_all_fks()
            count.fk = fk_count
            self.changed += fk_count
            self.covers_changed += self.update_custom_covers()
            self.covers_changed += self.create_custom_covers()

            comic_count = self.update_comics()
            comic_count += self.create_comics()
            count.comic = comic_count
            self.changed += comic_count

            ########
            # LINK #
            ########
            link_count = self.link_comic_m2m_fields()
            count.link = link_count
            self.link_custom_covers()
            self.changed += fk_count + comic_count + link_count

            new_failed_imports = self.fail_imports()

            deleted_count, deleted_comic_groups = self.delete()
            self.changed += deleted_count
            count.deleted = deleted_count

            self.changed += self.update_all_groups(
                deleted_comic_groups, self.start_time
            )
        finally:
            self._finish_apply(count, new_failed_imports=new_failed_imports)
