"""Prepare FTS update methods used in earlier import steps."""

from codex.librarian.scribe.importer.const import (
    CREDITS_FIELD_NAME,
    FTS_CREATE,
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_FIELD_TARGETS,
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
    def minify_complex_link_to_fts_tuple(
        field_name: str, values: tuple | frozenset
    ) -> tuple[str, tuple]:
        """Only store the fts relevant parts of complex links."""
        if field_name == CREDITS_FIELD_NAME:
            values = tuple(subvalues[0] for subvalues in values)
        elif field_name == STORY_ARC_NUMBERS_FIELD_NAME:
            field_name = STORY_ARC_FIELD_NAME + "s"
        return field_name, tuple(values)

    @staticmethod
    def _to_fts_tuple(values) -> tuple:
        return tuple(
            sorted(value for value in flatten(values) if isinstance(value, str))
        )

    @staticmethod
    def _iter_fts_targets(
        field_name: str, values: tuple
    ) -> tuple[tuple[str, tuple], ...]:
        """
        Expand one source field into its ComicFTS target columns.

        Most fields map to a single column of the same name (identity).
        Entries in :data:`FTS_FIELD_TARGETS` can fan out to multiple columns
        and optionally rewrite the value tuple per target.
        """
        targets = FTS_FIELD_TARGETS.get(field_name)
        if not targets:
            return ((field_name, values),)
        expanded = []
        for target_name, transform in targets:
            target_values = transform(values) if transform else values
            expanded.append((target_name, target_values))
        return tuple(expanded)

    def add_to_fts_existing(self, pk: int, field_name: str, values: tuple) -> None:
        """Add the existing values for creating a changed search entry."""
        if field_name in NON_FTS_FIELDS or not values:
            return
        field_name, values = self.minify_complex_link_to_fts_tuple(field_name, values)
        for fts_field_name, target_values in self._iter_fts_targets(field_name, values):
            fts_values = self._to_fts_tuple(target_values)
            if not fts_values:
                continue
            if pk not in self.metadata[FTS_EXISTING_M2MS]:
                self.metadata[FTS_EXISTING_M2MS][pk] = {}
            self.metadata[FTS_EXISTING_M2MS][pk][fts_field_name] = fts_values

    def add_links_to_fts(
        self,
        sub_key: int | str,
        field_name: str,
        values: tuple[str | tuple, ...],
    ) -> None:
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
        combined_values = flat_values + extra_values
        for fts_field_name, target_values in self._iter_fts_targets(
            field_name, combined_values
        ):
            fts_values = self._to_fts_tuple(target_values)
            self.metadata[key][sub_key][fts_field_name] = fts_values
