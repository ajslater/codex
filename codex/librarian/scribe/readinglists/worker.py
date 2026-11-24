"""Run reading list scribe tasks."""

from time import time
from typing import ClassVar

from django.contrib.auth.models import User
from django.db.models import Q

from codex.librarian.notifier.tasks import (
    LIBRARY_CHANGED_TASK,
    READING_LISTS_CHANGED_TASK,
)
from codex.librarian.scribe.readinglists.combine import recombine, rematch
from codex.librarian.scribe.readinglists.errors import add_reading_list_error
from codex.librarian.scribe.readinglists.live import sync_live
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    import_document,
    refresh_source,
)
from codex.librarian.scribe.readinglists.status import (
    ReadingListImportStatus,
    ReadingListLiveStatus,
    ReadingListMatchStatus,
)
from codex.librarian.scribe.readinglists.tasks import (
    ImportItem,
    ReadingListImportTask,
    ReadingListLiveSyncTask,
    ReadingListRecombineTask,
    ReadingListRematchTask,
)
from codex.librarian.worker import WorkerStatusBase
from codex.models.readinglist import ReadingList, ReadingListSource


class ReadingListWorker(WorkerStatusBase):
    """Store, recombine and rematch reading lists."""

    def _import_item(self, item: ImportItem, matcher: ListMatcher) -> bool:
        if item.source_pk is not None:
            source = (
                ReadingListSource.objects.filter(pk=item.source_pk)
                .select_related("reading_list")
                .first()
            )
            if source is None:
                return False
            return refresh_source(source, item.document, matcher)
        if not item.document:
            return False
        into = (
            ReadingList.objects.filter(pk=item.into_pk).first()
            if item.into_pk
            else None
        )
        user = User.objects.filter(pk=item.user_pk).first() if item.user_pk else None
        spec = SourceSpec.of(item.document, item.kind, item.ref)
        import_document(
            item.document, spec, into=into, user=user, name=item.name, matcher=matcher
        )
        return True

    def import_lists(self, task: ReadingListImportTask) -> None:
        """Store each delivered list; one that fails does not stop the rest."""
        status = ReadingListImportStatus(0, len(task.items))
        self.status_controller.start(status)
        changed = 0
        try:
            matcher = ListMatcher()
            for item in task.items:
                try:
                    changed += int(self._import_item(item, matcher))
                except Exception as exc:
                    self.log.exception(f"Importing reading list {item.kind}:{item.ref}")
                    add_reading_list_error(item.kind, item.ref, str(exc))
                status.increment_complete()
                self.status_controller.update(status)
        finally:
            self.status_controller.finish(status)
            self._notify(changed=bool(changed))
        self.log.info(f"Imported {changed} of {len(task.items)} reading lists.")

    def recombine_lists(self, task: ReadingListRecombineTask) -> None:
        """Recompute lists from their sources."""
        status = ReadingListImportStatus(0, len(task.list_pks))
        self.status_controller.start(status)
        try:
            matcher = ListMatcher()
            for reading_list in ReadingList.objects.filter(pk__in=task.list_pks):
                recombine(reading_list, matcher)
                status.increment_complete()
                self.status_controller.update(status)
        finally:
            self.status_controller.finish(status)
            self._notify(changed=True)

    # When the last full rematch began, in this process: one starts after
    # the imports that queued it committed, so it covers every full
    # rematch queued before it began.
    _full_rematch_began: ClassVar[float] = 0.0

    def _covered(self, task: ReadingListRematchTask) -> bool:
        """Whether a full rematch since began after this one was queued."""
        if task.list_pks:
            return False
        if task.queued_at < ReadingListWorker._full_rematch_began:
            self.log.debug("A full reading list rematch since covers this one.")
            return True
        ReadingListWorker._full_rematch_began = time()
        return False

    def rematch_lists(self, task: ReadingListRematchTask) -> None:
        """Match missing entries again across the given lists, or every list."""
        if self._covered(task):
            return
        lists = ReadingList.objects.filter(
            Q(
                entries__comic__isnull=True,
                entries__ignored=False,
                entries__live_source__isnull=True,
            )
        ).distinct()
        if task.list_pks:
            lists = lists.filter(pk__in=task.list_pks)
        lists = list(lists)
        status = ReadingListMatchStatus(0, len(lists))
        self.status_controller.start(status)
        found = 0
        try:
            matcher = ListMatcher()
            for reading_list in lists:
                found += rematch(reading_list, matcher)
                status.increment_complete()
                self.status_controller.update(status)
        finally:
            self.status_controller.finish(status)
            if found:
                self._notify(changed=True)
        if found:
            self.log.info(f"Matched {found} reading list issues.")

    def sync_live_lists(self, task: ReadingListLiveSyncTask) -> None:
        """Sync the comics of lists' collection items."""
        status = ReadingListLiveStatus(0, None)
        self.status_controller.start(status)
        changed = 0
        try:
            changed = sync_live(force=task.force, list_pks=task.list_pks or None)
        finally:
            self.status_controller.finish(status)
            if changed:
                self._notify(changed=True)
        if changed:
            self.log.info(f"Synced the collections of {changed} reading lists.")

    def _notify(self, *, changed: bool) -> None:
        self.librarian_queue.put(READING_LISTS_CHANGED_TASK)
        if changed:
            self.librarian_queue.put(LIBRARY_CHANGED_TASK)

    def handle_task(self, task) -> None:
        """Dispatch a reading list task."""
        match task:
            case ReadingListImportTask():
                self.import_lists(task)
            case ReadingListRecombineTask():
                self.recombine_lists(task)
            case ReadingListRematchTask():
                self.rematch_lists(task)
            case ReadingListLiveSyncTask():
                self.sync_live_lists(task)
            case _:
                self.log.warning(f"Unknown reading list task {task}")
