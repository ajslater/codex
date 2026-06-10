"""Prune M2O links that don't need updating."""

from comicbox.formats.comicbox.schema import PROTAGONIST_KEY

from codex.librarian.scribe.importer.const import (
    COMIC_FK_FIELD_NAMES,
    FIELD_NAME_KEYS_REL_MAP,
    LINK_FKS,
    PATH_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
)
from codex.librarian.scribe.importer.query.update_comics import QueryUpdateComics
from codex.models.comic import Comic
from codex.settings import (
    IMPORTER_LINK_FK_BATCH_SIZE,
    IMPORTER_LINK_M2M_BATCH_SIZE,
)

_PROTAGONIST_VALUE_PATHS = tuple(
    f"{field_name}__name" for field_name in PROTAGONIST_FIELD_MODEL_MAP
)


class QueryPruneLinksFKs(QueryUpdateComics):
    """
    Prune M2O links that don't need updating.

    Compares existing FK links as values tuples from one batched query
    — every referenced field's key rels joined in SQL — instead of
    walking instance getattr chains, which lazy-loaded a SELECT per
    relation hop past the shallow ``select_related`` (e.g. volume →
    series → imprint → publisher, per comic).
    """

    def _build_fk_value_plan(
        self,
    ) -> tuple[tuple[str, ...], tuple[tuple[str, int, int], ...]]:
        """
        Build the values_list columns and per-field row spans.

        Only fields actually referenced by the import are queried; most
        imports only touch a few FKs per comic.
        """
        referenced: set[str] = set()
        for path_link in self.metadata[LINK_FKS].values():
            referenced.update(path_link)
        cols: list[str] = [PATH_FIELD_NAME]
        spans: list[tuple[str, int, int]] = []
        start = 1
        for field_name in (PROTAGONIST_KEY, *COMIC_FK_FIELD_NAMES):
            if field_name not in referenced:
                continue
            value_paths = (
                _PROTAGONIST_VALUE_PATHS
                if field_name == PROTAGONIST_KEY
                else tuple(
                    f"{field_name}__{rel}"
                    for rel in FIELD_NAME_KEYS_REL_MAP[field_name]
                )
            )
            end = start + len(value_paths)
            cols.extend(value_paths)
            spans.append((field_name, start, end))
            start = end
        return tuple(cols), tuple(spans)

    @staticmethod
    def _fk_key_values_equal(
        field_name: str, key_values: tuple, row: tuple, start: int, end: int
    ) -> bool:
        """Compare proposed key values against the existing link's."""
        if field_name == PROTAGONIST_KEY:
            # The protagonist matches if either the main character or
            # the main team already carries the name.
            prot = key_values[0]
            return prot is not None and prot in row[start:end]
        return row[start:end] == key_values

    def _query_prune_comic_fk_links_row(
        self, row: tuple, spans: tuple[tuple[str, int, int], ...], status
    ) -> None:
        """Prune one comic's fk links."""
        path = row[0]
        link_fks = self.metadata[LINK_FKS].get(path)
        if link_fks is None:
            self.log.error(
                f"Tried to link foreign keys to path that's not in the LINK_FKS tags {path}"
            )
            return
        count = 0
        for field_name, start, end in spans:
            key_values = link_fks.get(field_name)
            if key_values is None:
                continue
            count += 1
            if self._fk_key_values_equal(field_name, key_values, row, start, end):
                # Already linked correctly: remove from the action set.
                del link_fks[field_name]
        status.increment_complete(count)
        # Refresh the controller once per comic — the controller already
        # rate-limits at _UPDATE_DELTA, so calling it inside the
        # per-FK-field loop only burns CPU on the early-return path.
        self.status_controller.update(status)
        if not link_fks:
            del self.metadata[LINK_FKS][path]

    def _query_prune_comic_fk_links_batch(
        self,
        batch_paths: tuple[str, ...],
        cols: tuple[str, ...],
        spans: tuple[tuple[str, int, int], ...],
        status,
    ) -> None:
        rows = (
            Comic.objects.filter(library=self.library, path__in=batch_paths)
            .values_list(*cols)
            .iterator(chunk_size=IMPORTER_LINK_M2M_BATCH_SIZE)
        )
        for row in rows:
            self._query_prune_comic_fk_links_row(row, spans, status)

    def query_prune_comic_fk_links(self, status) -> None:
        """Prune comic fk links that already exist."""
        status.subtitle = "Many to One"
        self.status_controller.update(status)
        cols, spans = self._build_fk_value_plan()
        if not spans:
            return
        paths = tuple(self.metadata[LINK_FKS].keys())
        num_paths = len(paths)

        start = 0
        while start < num_paths:
            if self.abort_event.is_set():
                return
            end = start + IMPORTER_LINK_FK_BATCH_SIZE
            batch_paths = paths[start:end]
            self._query_prune_comic_fk_links_batch(batch_paths, cols, spans, status)
            start += IMPORTER_LINK_FK_BATCH_SIZE
