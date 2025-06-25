"""Prune M2M links that don't need updating."""

from codex.librarian.scribe.importer.const import (
    COMIC_M2M_FIELD_RELS,
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
    ):
        """Remove existing m2m links from the action list and add missing ones delete list."""
        # transform objs into tuples
        key_attrs = FIELD_NAME_KEY_ATTRS_MAP[field_name]
        existing_key_value_tuple = self._m2m_obj_to_key_tuple(key_attrs, m2m_obj)
        field_proposed_values = self.metadata[LINK_M2MS][comic.path][field_name]
        if existing_key_value_tuple in field_proposed_values:
            # If already linked correctly, remove from action set
            field_proposed_values.discard(existing_key_value_tuple)
        else:
            # Delete existing m2m links that aren't in the new comic
            delete_m2m = (comic.pk, m2m_obj.pk)
            self.metadata[DELETE_M2MS][field_name].add(delete_m2m)

    def _query_prune_comic_m2m_links_field(self, comic: Comic, field_name: str, status):
        if field_name not in self.metadata[DELETE_M2MS]:
            self.metadata[DELETE_M2MS][field_name] = set()

        m2m_objs = getattr(comic, field_name).all()
        for m2m_obj in m2m_objs:
            self._query_prune_comic_m2m_links_field_obj(comic, field_name, m2m_obj)
            status.increment_complete()
            self.status_controller.update(status)
        if not self.metadata[LINK_M2MS][comic.path][field_name]:
            del self.metadata[LINK_M2MS][comic.path][field_name]

    def _query_prune_comic_m2m_links_comic(self, comic: Comic, status):
        field_names = tuple(self.metadata[LINK_M2MS][comic.path].keys())
        for field_name in field_names:
            self._query_prune_comic_m2m_links_field(comic, field_name, status)
        if not self.metadata[LINK_M2MS][comic.path]:
            del self.metadata[LINK_M2MS][comic.path]

    def _query_prune_comic_m2m_links_batch(self, batch_paths: tuple[str], status):
        comics = (
            Comic.objects.filter(library=self.library, path__in=batch_paths)
            .prefetch_related(*COMIC_M2M_FIELD_RELS)
            .only(*COMIC_M2M_FIELD_RELS)
        )
        for comic in comics:
            self._query_prune_comic_m2m_links_comic(comic, status)

    def _query_prune_comic_m2m_links(self, status):
        status.subtitle = "Many to Many"
        self.status_controller.update(status)
        paths = tuple(self.metadata[LINK_M2MS].keys())
        num_paths = len(paths)
        # Use comic objects because it helps naturally segregate deep objects into
        # objects for comparing with tuples.
        start = 0
        while start < num_paths:
            end = start + LINK_M2M_BATCH_SIZE
            batch_paths = paths[start:end]
            self._query_prune_comic_m2m_links_batch(batch_paths, status)
            start += LINK_M2M_BATCH_SIZE

        field_names = tuple(self.metadata[DELETE_M2MS].keys())
        for field_name in field_names:
            rows = self.metadata[DELETE_M2MS][field_name]
            if not rows:
                del self.metadata[DELETE_M2MS][field_name]
            status.increment_complete()
        self.status_controller.update(status)
