"""Search Index update."""

from collections.abc import Mapping
from itertools import batched
from time import perf_counter

from humanize import naturaldelta

from codex.librarian.scribe.importer.const import (
    FTS_CREATE,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
    FTS_UPDATED_M2MS,
    UNIVERSES_FIELD_NAME,
)
from codex.librarian.scribe.importer.search.sync_m2m import (
    SearchIndexSyncManyToManyImporter,
)
from codex.librarian.scribe.importer.statii.search import (
    ImporterFTSCreateStatus,
    ImporterFTSStatus,
    ImporterFTSUpdateStatus,
)
from codex.librarian.scribe.search.prepare import SearchEntryPrepare
from codex.librarian.status import Status
from codex.models.comic import ComicFTS
from codex.models.named import Universe
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE


class SearchIndexCreateUpdateImporter(SearchIndexSyncManyToManyImporter):
    """Search Index update methods."""

    def _get_universe_designations(self, entries: Mapping[int, dict]) -> dict:
        """
        Map the names of the universes these entries index to designations.

        The index holds each universe's designation beside its name, as a
        full rebuild writes it. The link phase only knows the names, so look
        up every one this pass touches, new, existing or kept, in batches.
        """
        existing = self.metadata.get(FTS_EXISTING_M2MS, {})
        names = set()
        for pk, entry in entries.items():
            names.update(entry.get(UNIVERSES_FIELD_NAME, ()))
            names.update(existing.get(pk, {}).get(UNIVERSES_FIELD_NAME, ()))
        designations = {}
        for batch in batched(sorted(names), IMPORTER_LINK_FK_BATCH_SIZE):
            designations.update(
                Universe.objects.filter(name__in=batch)
                .exclude(designation="")
                .values_list("name", "designation")
            )
        return designations

    @staticmethod
    def _add_universe_designations(
        entry: dict, existing_m2m_values: dict | None, designations: Mapping
    ) -> None:
        """Index the designations of the entry's new and kept universes."""
        names = (
            *entry.get(UNIVERSES_FIELD_NAME, ()),
            *(existing_m2m_values or {}).get(UNIVERSES_FIELD_NAME, ()),
        )
        if found := {designations[name] for name in names if name in designations}:
            entry[UNIVERSES_FIELD_NAME] = (
                *entry.get(UNIVERSES_FIELD_NAME, ()),
                *sorted(found),
            )

    def _create_comicfts_entry(
        self,
        pk: int,
        entry: dict,
        obj_list: list[ComicFTS],
        status: Status,
        designations: Mapping,
    ) -> None:
        if entry:
            existing_m2m_values = self.metadata[FTS_EXISTING_M2MS].get(pk)
            self._add_universe_designations(entry, existing_m2m_values, designations)
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
        designations: Mapping,
    ) -> None:
        comic_id = comicfts.comic_id  # pyright:ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        # ``codex_comicfts`` is an FTS5 virtual table without a unique
        # constraint on ``comic_id``; the queryset can yield the same
        # comic_id more than once if the table contains duplicate rows
        # (or when an iteration sees a row whose entry was already
        # consumed for another reason). Treat "missing key" the same
        # as "empty entry" — both mean "nothing to write for this row".
        if entry := self.metadata[FTS_UPDATE].pop(comic_id, None):
            existing_m2m_values = self.metadata[FTS_EXISTING_M2MS].get(comic_id)
            self._add_universe_designations(entry, existing_m2m_values, designations)
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
        designations = self._get_universe_designations(entries)
        for pk in pks:
            entry = entries.pop(pk)
            self._create_comicfts_entry(pk, entry, obj_list, status, designations)
        return tuple(obj_list), pks

    def _update_search_index_operate_update(
        self, status: ImporterFTSStatus
    ) -> tuple[tuple[ComicFTS, ...], tuple[int, ...]]:
        obj_list = []
        if pks := tuple(sorted(self.metadata.get(FTS_UPDATE, {}).keys())):
            comicftss = ComicFTS.objects.filter(comic_id__in=pks)
            if self.abort_event.is_set():
                return tuple(obj_list), ()
            designations = self._get_universe_designations(self.metadata[FTS_UPDATE])
            for comicfts in comicftss:
                self._update_comicfts_entry(comicfts, obj_list, status, designations)
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
            # Replace updates with delete + bulk_create. FTS5 makes
            # ``bulk_update``'s CASE-WHEN UPDATE expensive (parser cost
            # in rows x cols, plus an internal delete+reinsert per
            # affected row at the segment level), and a multi-row
            # INSERT cuts wall time roughly 1.5-3x on real workloads.
            # Inherits ``_delete_then_create_comicfts`` from
            # ``SearchIndexSyncManyToManyImporter`` for the atomic
            # swap and chunked DELETE.
            self._delete_then_create_comicfts(list(obj_list))
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

    def _update_search_index(self, cleaned_count: int) -> None:
        """Update or Rebuild the search index."""
        start_time = perf_counter()
        if self.abort_event.is_set():
            return
        updated_count = self._update_search_index_update()
        if self.abort_event.is_set():
            return
        created_count = self._update_search_index_create()

        elapsed_time = perf_counter() - start_time
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

    def import_search_index(self, cleaned_count: int) -> None:
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
            # An operate with no entries returns before it consumes its
            # inputs; an import that rewrote no comics leaves them empty.
            for key in (FTS_CREATE, FTS_UPDATE, FTS_UPDATED_M2MS, FTS_EXISTING_M2MS):
                self.metadata.pop(key, None)
            self.status_controller.finish_many(
                (ImporterFTSCreateStatus, ImporterFTSUpdateStatus)
            )
