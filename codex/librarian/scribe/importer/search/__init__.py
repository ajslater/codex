"""Sync the fts index with the imported database."""

from codex.librarian.scribe.importer.const import (
    CREDITS_FIELD_NAME,
    FTS_CREATE,
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
    IDENTIFIERS_FIELD_NAME,
    NON_FTS_FIELDS,
    STORY_ARC_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
)
from codex.librarian.scribe.importer.search.update import (
    SearchIndexCreateUpdateImporter,
)
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.scribe.search.handler import SearchIndexer
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status
from codex.util import flatten

_STATII = (
    Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAN),
    Status(ImporterStatusTypes.SEARCH_INDEX_UPDATE),
    Status(ImporterStatusTypes.SEARCH_INDEX_CREATE),
)


class SearchIndexImporter(SearchIndexCreateUpdateImporter):
    """Sync the fts index with the imported database."""

    @staticmethod
    def minify_complex_link_to_fts_tuple(field_name: str, values: tuple | frozenset):
        """Only store the fts relevant parts of complex links."""
        if field_name == CREDITS_FIELD_NAME:
            values = tuple(subvalues[0] for subvalues in values)
        if field_name == IDENTIFIERS_FIELD_NAME:
            values = tuple(subvalues[-1] for subvalues in values)
        elif field_name == STORY_ARC_NUMBERS_FIELD_NAME:
            field_name = STORY_ARC_FIELD_NAME + "s"
        return field_name, tuple(values)

    @staticmethod
    def _to_fts_tuple(values):
        return tuple(
            sorted(value for value in flatten(values) if isinstance(value, str))
        )

    def add_to_fts_existing(self, pk: int, field_name: str, values: tuple):
        """Add the existing values for creating a changed search entry."""
        if field_name in NON_FTS_FIELDS or not values:
            return
        if field_name == IDENTIFIERS_FIELD_NAME:
            # sources extracton must come before identifiers is minified
            sources = tuple(subvalues[0] for subvalues in values)
            self.add_to_fts_existing(pk, "sources", sources)
        field_name, values = self.minify_complex_link_to_fts_tuple(field_name, values)
        fts_values = self._to_fts_tuple(values)
        if not fts_values:
            return
        if pk not in self.metadata[FTS_EXISTING_M2MS]:
            self.metadata[FTS_EXISTING_M2MS][pk] = {}
        self.metadata[FTS_EXISTING_M2MS][pk][field_name] = fts_values

    def add_links_to_fts(
        self,
        sub_key: int | str,
        field_name: str,
        values: tuple[str | tuple, ...],
    ):
        """Add a link to FTS structure."""
        if field_name in NON_FTS_FIELDS:
            return
        key = FTS_UPDATE if sub_key in self.metadata.get(FTS_UPDATE, {}) else FTS_CREATE
        flat_values = flatten(values)
        extra_values = (
            self.metadata[FTS_CREATED_M2MS].get(field_name, {}).pop(flat_values, ())
        )
        fts_values = self._to_fts_tuple(flat_values + extra_values)
        self.metadata[key][sub_key][field_name] = fts_values

    def clean_fts(self):
        """Clean search index of any deleted comics."""
        indexer = SearchIndexer(
            self.log, self.librarian_queue, self.db_write_lock, event=self.abort_event
        )
        indexer.remove_stale_records()

    def full_text_search(self):
        """Sync the fts index with the imported database."""
        self.status_controller.start_many(_STATII)
        try:
            self.clean_fts()
            self.import_search_index()
        finally:
            self.status_controller.finish_many(_STATII)
