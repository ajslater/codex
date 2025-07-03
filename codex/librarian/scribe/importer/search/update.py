"""Search Index update."""

from time import time

from comicbox.identifiers import ID_SOURCE_NAME_MAP
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
from codex.librarian.scribe.importer.status import ImporterStatusTypes
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
        for source in sources:
            names.append(source)
            if long_name := ID_SOURCE_NAME_MAP.get(source):
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
        comic_id = comicfts.comic_id  # pyright:ignore[reportAttributeAccessIssue]
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

    def _update_search_index_create_or_update(
        self,
        obj_list: list[ComicFTS],
        status,
        *,
        create: bool,
    ):
        if self.abort_event.is_set():
            return
        verb = "create" if create else "update"
        verbing = (verb[:-1] + "ing").capitalize()
        num_comic_fts = len(obj_list)

        batch_position = f"({status.complete}/{status.total})"
        self.log.debug(f"{verbing} {num_comic_fts} {batch_position} search entries...")
        if create:
            ComicFTS.objects.bulk_create(obj_list)
        else:
            ComicFTS.objects.bulk_update(obj_list, COMICFTS_UPDATE_FIELDS)
        obj_list.clear()

    def _update_search_index_finish(self, status, *, create: bool):
        verb = "create" if create else "update"
        verbed = verb.capitalize() + "d"
        suffix = f"search entries in {status.elapsed()}"

        if status.complete:
            eps = status.per_second("entries")
            self.log.info(f"{verbed} {status.complete} {suffix}, {eps}.")
        else:
            self.log.debug(f"{verbed} no {suffix}.")
        self.status_controller.finish(status)

    def _update_search_index_operate_get_status(
        self, total_entries: int, *, create: bool
    ):
        status_type = (
            ImporterStatusTypes.SEARCH_INDEX_CREATE
            if create
            else ImporterStatusTypes.SEARCH_INDEX_UPDATE
        )
        return Status(status_type, total=total_entries)

    def _update_search_index_operate(self, *, create: bool) -> tuple[int, ...]:
        key = FTS_CREATE if create else FTS_UPDATE
        total_entries = len(self.metadata.get(key, {}))
        status = self._update_search_index_operate_get_status(
            total_entries, create=create
        )
        updated_pks = ()
        try:
            verb = "create" if create else "update"
            if not total_entries:
                self.log.info(f"No search entries to {verb}.")
                return updated_pks
            self.status_controller.start(status)

            obj_list = []
            if create:
                entries = self.metadata.pop(FTS_CREATE, {})
                pks = tuple(entries.keys())
                for pk in pks:
                    if self.abort_event.is_set():
                        return updated_pks
                    entry = entries.pop(pk)
                    self._create_comicfts_entry(pk, entry, obj_list, status)
                updated_pks = pks
            else:
                comic_ids = tuple(self.metadata[FTS_UPDATE].keys())
                comicftss = ComicFTS.objects.filter(comic_id__in=comic_ids)
                for comicfts in comicftss:
                    if self.abort_event.is_set():
                        return tuple(updated_pks)
                    self._update_comicfts_entry(comicfts, obj_list, status)
                self.metadata.pop(FTS_UPDATE)

            self.log.debug(f"Preparing {total_entries} comics for search indexing...")
            self._update_search_index_create_or_update(
                obj_list,
                status,
                create=create,
            )

        finally:
            self._update_search_index_finish(status, create=create)
        return tuple(updated_pks)

    def _update_search_index_update(self):
        """Update out of date search entries."""
        self._update_search_index_operate(create=False)

    def _update_search_index_create(self):
        """Create missing search entries."""
        pks = self._update_search_index_operate(create=True)
        if self.abort_event.is_set():
            return
        self.sync_fts_for_m2m_updates(pks)

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
        updated = f"{updated_count} entries updated" if updated_count else ""
        created = f"{created_count} entries created" if created_count else ""
        cleaned = f"{cleaned_count} entries cleaned up" if cleaned_count else ""
        summary_parts = filter(None, (cleaned, updated, created))
        summary = ", ".join(summary_parts)
        self.log.success(f"Search index {summary} in {elapsed}.")

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
                (
                    ImporterStatusTypes.SEARCH_INDEX_UPDATE,
                    ImporterStatusTypes.SEARCH_INDEX_CREATE,
                )
            )
