"""Prune M2O links that don't need updating."""

from codex.librarian.scribe.importer.const import (
    COMIC_FK_FIELD_NAMES,
    FIELD_NAME_KEYS_REL_MAP,
    LINK_FKS,
    PATH_FIELD_NAME,
)
from codex.librarian.scribe.importer.query.update_comics import QueryUpdateComics
from codex.models.comic import Comic
from codex.settings import LINK_FK_BATCH_SIZE

_QUERY_LINK_FK_PRUNE_ONLY = (
    PATH_FIELD_NAME,
    *COMIC_FK_FIELD_NAMES,
)


class QueryPruneLinksFKs(QueryUpdateComics):
    """Prune M2O links that don't need updating."""

    def pop_links_to_fts(self, path, field_name):
        """Pop a link to the FTS structure."""
        link_key = self.metadata[LINK_FKS][path].pop(field_name)
        self.add_links_to_fts(path, field_name, (link_key,))

    def _query_prune_comic_fk_links_protagonist(
        self, comic: Comic, path: str, field_name: str, key_values: tuple
    ):
        prot = key_values[0]
        for obj in (comic.main_character, comic.main_team):
            if obj and obj.name == prot:
                self.metadata[LINK_FKS][path].pop(field_name)
                break

    @staticmethod
    def _query_prune_comic_fk_links_key_equal(field_obj, key_rel, key_value):
        parts = key_rel.split("__")
        rel_obj = field_obj
        key_val = None
        while parts:
            key_val = getattr(rel_obj, parts.pop(0), None)
            rel_obj = key_val
        return key_val == key_value

    def _query_prune_comic_fk_links_field(self, comic, path, field_name):
        link_dict = self.metadata[LINK_FKS].get(path)
        key_values = link_dict[field_name]
        if field_name == "protagonist":
            self._query_prune_comic_fk_links_protagonist(
                comic, path, field_name, key_values
            )
            return
        key_rels = FIELD_NAME_KEYS_REL_MAP[field_name]
        keys_equal = True
        field_obj = getattr(comic, field_name)
        for key_rel, key_value in zip(key_rels, key_values, strict=True):
            keys_equal = self._query_prune_comic_fk_links_key_equal(
                field_obj, key_rel, key_value
            )
            if not keys_equal:
                break
        if keys_equal:
            self.metadata[LINK_FKS][path].pop(field_name)

    def _query_prune_comic_fk_links_comic(self, comic, status):
        path = comic.path
        path_link_fks = self.metadata[LINK_FKS].get(path)
        if path_link_fks is None:
            self.log.error(
                f"Tried to link foreign keys to path that's not in the LINK_FKS metadata {path}"
            )
            return
        field_names = tuple(path_link_fks.keys())
        for field_name in field_names:
            self._query_prune_comic_fk_links_field(comic, path, field_name)
            status.increment_complete()
            self.status_controller.update(status)
        if not self.metadata[LINK_FKS][path]:
            del self.metadata[LINK_FKS][path]

    def _query_prune_comic_fk_links_batch(self, batch_paths: tuple[str, ...], status):
        comics = (
            Comic.objects.filter(library=self.library, path__in=batch_paths)
            .select_related(*COMIC_FK_FIELD_NAMES)
            .only(*_QUERY_LINK_FK_PRUNE_ONLY)
        )
        for comic in comics:
            self._query_prune_comic_fk_links_comic(comic, status)

    def query_prune_comic_fk_links(self, status):
        """Prune comic fk links that already exist."""
        status.subtitle = "Many to One"
        self.status_controller.update(status)
        paths = tuple(self.metadata[LINK_FKS].keys())
        num_paths = len(paths)

        start = 0
        while start < num_paths:
            if self.abort_event.is_set():
                return
            end = start + LINK_FK_BATCH_SIZE
            batch_paths = paths[start:end]
            self._query_prune_comic_fk_links_batch(batch_paths, status)
            start += LINK_FK_BATCH_SIZE
