"""Search Index update."""

from contextlib import suppress
from time import time

from comicbox.enums.comicbox import IdSources
from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from django.db.models.functions.datetime import Now
from humanize import naturaldelta

from codex.librarian.scribe.importer.const import (
    FTS_CREATE,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
)
from codex.librarian.scribe.importer.search.const import (
    COMICFTS_UPDATE_FIELDS,
    PYCOUNTRY_FIELDS,
)
from codex.librarian.scribe.importer.search.sync_m2m import (
    SearchIndexSyncManyToManyImporter,
)
from codex.librarian.scribe.importer.statii.search import (
    ImporterFTSCreateStatus,
    ImporterFTSStatus,
    ImporterFTSUpdateStatus,
)
from codex.librarian.status import Status
from codex.models.comic import ComicFTS


class SearchIndexCreateUpdateImporter(SearchIndexSyncManyToManyImporter):
    """Search Index update methods."""

    @staticmethod
    def _get_pycountry_fts_field(entry, field_name) -> str:
        iso_code = entry.get(field_name)
        if not iso_code:
            return ""
        field = PYCOUNTRY_FIELDS[field_name]
        return ",".join((iso_code, field.to_representation(iso_code)))

    @staticmethod
    def _get_sources_fts_field(entry) -> tuple[str, ...]:
        sources = entry.get("sources", ())
        names = []
        for source_str in sources:
            names.append(source_str)
            with suppress(ValueError):
                id_source = IdSources(source_str)
                if long_name := ID_SOURCE_NAME_MAP.get(id_source):
                    names.append(long_name)
        return tuple(names)

    @staticmethod
    def _create_comicfts_entry_attributes(entry, *, create: bool):
        now = Now()
        entry["updated_at"] = now
        if create:
            entry["created_at"] = now

    @classmethod
    def _create_comicfts_entry_fks(cls, entry):
        entry["country"] = cls._get_pycountry_fts_field(entry, "country")
        entry["language"] = cls._get_pycountry_fts_field(entry, "language")

    @staticmethod
    def _to_fts_values(value):
        """Create a tuple of fts value strings."""
        return tuple(
            subvalue
            for values_tuple in value
            for subvalue in values_tuple
            if isinstance(subvalue, str)
        )

    def _create_comicfts_entry_m2ms(self, pk: int, entry):
        if sources := self._get_sources_fts_field(entry):
            entry["sources"] = sources
        if existing_values := self.metadata[FTS_EXISTING_M2MS].get(pk):
            for field_name in tuple(existing_values.keys()):
                if values := existing_values.get(field_name):
                    entry[field_name] = entry.get(field_name, ()) + values

    def _create_comicfts_entry(
        self,
        pk,
        entry,
        obj_list: list[ComicFTS],
        status: Status,
    ):
        self._create_comicfts_entry_m2ms(pk, entry)
        for field_name in entry:
            value = entry[field_name]
            if isinstance(value, tuple):
                entry[field_name] = ",".join(sorted(value))
        self._create_comicfts_entry_attributes(entry, create=True)
        self._create_comicfts_entry_fks(entry)
        comicfts = ComicFTS(comic_id=pk, **entry)
        obj_list.append(comicfts)
        status.increment_complete()
        self.status_controller.update(status)

    def _update_comicfts_entry(
        self,
        comicfts: ComicFTS,
        obj_list: list[ComicFTS],
        status: Status,
    ):
        comic_id = comicfts.comic_id  # pyright:ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        entry = self.metadata[FTS_UPDATE].pop(comic_id)
        self._create_comicfts_entry_m2ms(comic_id, entry)
        for field_name in entry:
            value = entry[field_name]
            if isinstance(value, tuple):
                entry[field_name] = ",".join(sorted(value))
        self._create_comicfts_entry_attributes(entry, create=True)
        self._create_comicfts_entry_fks(entry)
        for field_name, value in entry.items():
            setattr(comicfts, field_name, value)
        obj_list.append(comicfts)
        status.increment_complete()
        self.status_controller.update(status)

    def _update_search_index_operate_get_status(
        self, total_entries: int, *, create: bool
    ) -> ImporterFTSStatus:
        status_class = ImporterFTSCreateStatus if create else ImporterFTSUpdateStatus
        return status_class(total=total_entries)

    def _update_search_index_operate_create(
        self, obj_list: list, status: ImporterFTSStatus
    ) -> tuple[int, ...]:
        entries = self.metadata.pop(FTS_CREATE, {})
        pks = tuple(entries.keys())
        for pk in pks:
            if self.abort_event.is_set():
                return ()
            entry = entries.pop(pk)
            self._create_comicfts_entry(pk, entry, obj_list, status)
        return pks

    def _update_search_index_operate_update(
        self, obj_list: list, status: ImporterFTSStatus
    ) -> tuple[int, ...]:
        if pks := tuple(self.metadata.get(FTS_UPDATE, {}).keys()):
            comicftss = ComicFTS.objects.filter(comic_id__in=pks)
            for comicfts in comicftss:
                if self.abort_event.is_set():
                    return ()
                self._update_comicfts_entry(comicfts, obj_list, status)
            if self.metadata[FTS_UPDATE]:
                # If updates not popped, turn them into creates.
                if FTS_CREATE not in self.metadata:
                    self.metadata[FTS_CREATE] = {}
                self.metadata[FTS_CREATE].update(self.metadata[FTS_UPDATE])
        self.metadata.pop(FTS_UPDATE)
        return pks

    def _update_search_index_create_or_update(
        self,
        obj_list: list[ComicFTS],
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
        count = len(obj_list)
        obj_list.clear()
        return count

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

            obj_list = []
            if create:
                update_pks = self._update_search_index_operate_create(obj_list, status)
            else:
                update_pks = self._update_search_index_operate_update(obj_list, status)
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
            if create:
                self.sync_fts_for_m2m_updates(update_pks)

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
            self.metadata.pop(FTS_EXISTING_M2MS)
            self.status_controller.finish_many(
                (ImporterFTSCreateStatus, ImporterFTSUpdateStatus)
            )
