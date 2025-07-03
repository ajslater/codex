"""Prune M2M links that don't need updating."""

from codex.librarian.scribe.importer.const import (
    COMIC_M2M_FIELD_NAMES,
    DELETE_M2MS,
    FIELD_NAME_KEY_ATTRS_MAP,
    LINK_M2MS,
)
from codex.librarian.scribe.importer.query.links_fk import QueryPruneLinksFKs
from codex.models.base import BaseModel, NamedModel
from codex.models.comic import Comic
from codex.models.groups import BrowserGroupModel
from codex.settings import LINK_M2M_BATCH_SIZE


class QueryPruneLinksM2M(QueryPruneLinksFKs):
    """Prune M2M links that don't need updating."""

    @staticmethod
    def _m2m_obj_to_key_tuple(key_attrs: tuple[str, ...], m2m_obj: BaseModel):
        """Create a key value tuple from a db obj."""
        value_tuple = []
        for attr in key_attrs:
            value = getattr(m2m_obj, attr)
            if isinstance(value, NamedModel | BrowserGroupModel):
                value = value.name
            value_tuple.append(value)
        return tuple(value_tuple)

    def _query_prune_comic_m2m_links_field_obj(
        self,
        comic: Comic,
        field_name: str,
        m2m_obj: BaseModel,
        kept_existing_values: set,
        proposed_values: set,
    ):
        """Remove existing m2m links from the action list and add missing ones delete list."""
        # transform objs into tuples
        key_attrs = FIELD_NAME_KEY_ATTRS_MAP[field_name]
        existing_key_value_tuple = self._m2m_obj_to_key_tuple(key_attrs, m2m_obj)
        if existing_key_value_tuple in proposed_values:
            # If already linked correctly, remove from action set
            kept_existing_values.add(existing_key_value_tuple)
            proposed_values.discard(existing_key_value_tuple)
            deleted = False
        else:
            # Delete existing m2m links that aren't in the new comic
            delete_m2m = (comic.pk, m2m_obj.pk)
            self.metadata[DELETE_M2MS][field_name].add(delete_m2m)
            deleted = True
        return deleted

    def _query_prune_comic_m2m_links_field(self, comic: Comic, field_name: str, status):
        if field_name not in self.metadata[DELETE_M2MS]:
            self.metadata[DELETE_M2MS][field_name] = set()

        m2m_objs = getattr(comic, field_name).all()
        deleted = False
        kept_existing_values = set()
        proposed_values = self.metadata[LINK_M2MS][comic.path][field_name]
        for m2m_obj in m2m_objs:
            deleted |= self._query_prune_comic_m2m_links_field_obj(
                comic, field_name, m2m_obj, kept_existing_values, proposed_values
            )
            status.increment_complete()
            self.status_controller.update(status)
        if kept_existing_values and (deleted or proposed_values):
            self.add_to_fts_existing(comic.pk, field_name, tuple(kept_existing_values))
        if not self.metadata[LINK_M2MS][comic.path][field_name]:
            del self.metadata[LINK_M2MS][comic.path][field_name]

    def _query_prune_comic_m2m_links_comic(self, comic: Comic, status):
        field_names = tuple(self.metadata[LINK_M2MS][comic.path].keys())
        for field_name in field_names:
            self._query_prune_comic_m2m_links_field(comic, field_name, status)
        if not self.metadata[LINK_M2MS][comic.path]:
            del self.metadata[LINK_M2MS][comic.path]

    def _query_prune_comic_m2m_links_batch(self, paths: tuple[str], status):
        comics = (
            Comic.objects.filter(library=self.library, path__in=paths)
            # prefetching deep links means a batch size of 190 or less
            .prefetch_related(*COMIC_M2M_FIELD_NAMES)
            .only(*COMIC_M2M_FIELD_NAMES)
        )
        for comic in comics.iterator(chunk_size=LINK_M2M_BATCH_SIZE):
            self._query_prune_comic_m2m_links_comic(comic, status)

    def query_prune_comic_m2m_links(self, status):
        """Prune comic m2m links that already exists or should be deleted."""
        status.subtitle = "Many to Many"
        self.status_controller.update(status)
        paths = tuple(self.metadata[LINK_M2MS].keys())
        self._query_prune_comic_m2m_links_batch(paths, status)
        field_names = tuple(self.metadata[DELETE_M2MS].keys())
        for field_name in field_names:
            rows = self.metadata[DELETE_M2MS][field_name]
            if not rows:
                del self.metadata[DELETE_M2MS][field_name]
        status.increment_complete(len(field_names))
        self.status_controller.update(status)
