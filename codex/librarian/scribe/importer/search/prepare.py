"""Prepare FTS update methods used in earlier import steps."""

from codex.librarian.scribe.importer.const import (
    CREDITS_FIELD_NAME,
    FTS_CREATE,
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
    NON_FTS_FIELDS,
    STORY_ARC_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
)
from codex.librarian.scribe.importer.search.update import (
    SearchIndexCreateUpdateImporter,
)
from codex.util import flatten


class SearchIndexPrepareImporter(SearchIndexCreateUpdateImporter):
    """Prepare FTS update methods used in earlier import steps."""

    @staticmethod
    def minify_complex_link_to_fts_tuple(field_name: str, values: tuple | frozenset):
        """Only store the fts relevant parts of complex links."""
        if field_name == CREDITS_FIELD_NAME:
            values = tuple(subvalues[0] for subvalues in values)
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
        if sub_key in self.metadata.get(FTS_UPDATE, {}):
            key = FTS_UPDATE
        elif sub_key in self.metadata.get(FTS_CREATE, {}):
            key = FTS_CREATE
        else:
            key = FTS_UPDATE
            if key not in self.metadata:
                self.metadata[key] = {}
            if sub_key not in self.metadata[key]:
                self.metadata[key][sub_key] = {}
            self.log.debug(
                f"FTS import anomaly, attempting FTS update for comic {sub_key} {field_name}"
            )
            # Alternative might be kicking off an FTS sync

        flat_values = flatten(values)
        extra_values = (
            self.metadata[FTS_CREATED_M2MS].get(field_name, {}).pop(flat_values, ())
        )
        fts_values = self._to_fts_tuple(flat_values + extra_values)
        self.metadata[key][sub_key][field_name] = fts_values
