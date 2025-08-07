"""Search Index update."""

from time import time

from humanize import naturaldelta

from codex.librarian.scribe.importer.const import (
    FTS_CREATE,
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
)
from codex.librarian.scribe.importer.search.sync_m2m import (
    SearchIndexSyncManyToManyImporter,
)
from codex.librarian.scribe.importer.statii.search import (
    ImporterFTSCreateStatus,
    ImporterFTSStatus,
    ImporterFTSUpdateStatus,
)
from codex.librarian.scribe.search.const import COMICFTS_UPDATE_FIELDS
from codex.librarian.scribe.search.prepare import SearchEntryPrepare
from codex.librarian.status import Status
from codex.models.comic import ComicFTS


class SearchIndexCreateUpdateImporter(SearchIndexSyncManyToManyImporter):
    """Search Index update methods."""

    def _create_comicfts_entry(
        self,
        pk: int,
        entry: dict,
        obj_list: list[ComicFTS],
        status: Status,
    ):
        if entry:
            existing_m2m_values = self.metadata[FTS_EXISTING_M2MS].get(pk)
            SearchEntryPrepare.prepare_import_fts_entry(
                pk, entry, existing_m2m_values, None, obj_list, status, create=True
            )
        else:
            status.decrement_total()
        self.status_controller.update(status)

    def _update_comicfts_entry(
        self,
        comicfts: ComicFTS,
        obj_list: list[ComicFTS],
        status: Status,
    ):
        comic_id = comicfts.comic_id  # pyright:ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if entry := self.metadata[FTS_UPDATE].pop(comic_id):
            existing_m2m_values = self.metadata[FTS_EXISTING_M2MS].get(comic_id)
            SearchEntryPrepare.prepare_import_fts_entry(
                comic_id,
                entry,
                existing_m2m_values,
                comicfts,
                obj_list,
                status,
                create=False,
            )
        else:
            status.decrement_total()
        self.status_controller.update(status)

    def _update_search_index_operate_get_status(
        self, total_entries: int, *, create: bool
    ) -> ImporterFTSStatus:
        status_class = ImporterFTSCreateStatus if create else ImporterFTSUpdateStatus
        return status_class(total=total_entries)

    def _update_search_index_operate_create(
        self, status: ImporterFTSStatus
    ) -> tuple[tuple[ComicFTS, ...], tuple[int, ...]]:
        entries = self.metadata.pop(FTS_CREATE, {})
        pks = tuple(sorted(entries.keys()))
        obj_list = []
        if self.abort_event.is_set():
            return tuple(obj_list), ()
        for pk in pks:
            entry = entries.pop(pk)
            self._create_comicfts_entry(pk, entry, obj_list, status)
        return tuple(obj_list), pks

    def _update_search_index_operate_update(
        self, status: ImporterFTSStatus
    ) -> tuple[tuple[ComicFTS, ...], tuple[int, ...]]:
        obj_list = []
        if pks := tuple(sorted(self.metadata.get(FTS_UPDATE, {}).keys())):
            comicftss = ComicFTS.objects.filter(comic_id__in=pks)
            if self.abort_event.is_set():
                return tuple(obj_list), ()
            for comicfts in comicftss:
                self._update_comicfts_entry(comicfts, obj_list, status)
            if self.metadata[FTS_UPDATE]:
                # If updates not popped, turn them into creates.
                if FTS_CREATE not in self.metadata:
                    self.metadata[FTS_CREATE] = {}
                self.metadata[FTS_CREATE].update(self.metadata[FTS_UPDATE])
        self.metadata.pop(FTS_UPDATE)
        return tuple(obj_list), ()

    def _update_search_index_create_or_update(
        self,
        obj_list: tuple[ComicFTS, ...],
        status,
        *,
        create: bool,
    ) -> int:
        if not obj_list or self.abort_event.is_set():
            return 0
        verb = "create" if create else "update"
        verbing = (verb[:-1] + "ing").capitalize()
        num_comic_fts = len(obj_list)

        batch_position = f"({status.complete}/{status.total})"
        self.log.debug(f"{verbing} {num_comic_fts} {batch_position} search entries...")
        if create:
            ComicFTS.objects.bulk_create(obj_list)
        else:
            ComicFTS.objects.bulk_update(obj_list, COMICFTS_UPDATE_FIELDS)
        return len(obj_list)

    def _update_search_index_operate(self, *, create: bool) -> int:
        key = FTS_CREATE if create else FTS_UPDATE
        total_entries = len(self.metadata.get(key, {}))
        status = self._update_search_index_operate_get_status(
            total_entries, create=create
        )
        count = 0
        try:
            verb = "create" if create else "update"
            if not total_entries:
                self.log.debug(f"No search entries to {verb}.")
                return count
            self.status_controller.start(status)
            verbing = "creating" if create else "updating"
            self.log.debug(
                f"Preparing {total_entries} comics for search index {verbing}..."
            )

            if create:
                obj_list, created_comic_pks = self._update_search_index_operate_create(
                    status
                )
            else:
                obj_list, created_comic_pks = self._update_search_index_operate_update(
                    status
                )
            self.log.debug(
                f"Prepared {len(obj_list)} comics for search index {verbing}..."
            )
            if self.abort_event.is_set():
                return count

            count = self._update_search_index_create_or_update(
                obj_list,
                status,
                create=create,
            )
            self.sync_fts_for_m2m_updates(created_comic_pks)

        finally:
            self.status_controller.finish(status)
        return count

    def _update_search_index_update(self) -> int:
        """Update out of date search entries."""
        return self._update_search_index_operate(create=False)

    def _update_search_index_create(self) -> int:
        """Create missing search entries."""
        return self._update_search_index_operate(create=True)

    def _update_search_index(self, cleaned_count: int):
        """Update or Rebuild the search index."""
        start_time = time()
        if self.abort_event.is_set():
            return
        updated_count = self._update_search_index_update()
        if self.abort_event.is_set():
            return
        created_count = self._update_search_index_create()

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        cleaned = f"{cleaned_count} cleaned up" if cleaned_count else ""
        updated = f"{updated_count} updated" if updated_count else ""
        created = f"{created_count} created" if created_count else ""
        summary_parts = filter(None, (cleaned, updated, created))
        if summary := ", ".join(summary_parts):
            level = "INFO"
            log_txt = f"Search index entries {summary}"
        else:
            level = "DEBUG"
            log_txt = "Nothing done to Search index"
        log_txt += f" in {elapsed}."
        self.log.log(level, log_txt)

    def import_search_index(self, cleaned_count: int):
        """Update or Rebuild the search index."""
        self.abort_event.clear()
        try:
            self._update_search_index(cleaned_count)
        except Exception:
            self.log.exception("Update search index")
        finally:
            if self.abort_event.is_set():
                self.log.info("Search Index update aborted early.")
            self.abort_event.clear()
            self.metadata.pop(FTS_EXISTING_M2MS, None)
            self.metadata.pop(FTS_CREATED_M2MS, None)
            self.status_controller.finish_many(
                (ImporterFTSCreateStatus, ImporterFTSUpdateStatus)
            )
