"""Prune M2M links that don't need updating."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from codex.librarian.scribe.importer.const import (
    COMIC_M2M_FIELD_NAMES,
    DELETE_M2MS,
    FIELD_NAME_KEY_ATTRS_MAP,
    FOLDERS_FIELD_NAME,
    LINK_M2MS,
    STORY_ARC_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
    get_through_model,
)
from codex.librarian.scribe.importer.query.links_fk import QueryPruneLinksFKs
from codex.models.base import NamedModel
from codex.models.collections import BrowserCollectionModel, Folder
from codex.models.comic import Comic
from codex.models.named import StoryArc
from codex.settings import (
    IMPORTER_LINK_FK_BATCH_SIZE,
    IMPORTER_LINK_M2M_BATCH_SIZE,
)

if TYPE_CHECKING:
    from django.db.models.fields.related import ManyToManyField


class QueryPruneLinksM2M(QueryPruneLinksFKs):
    """
    Prune M2M links that don't need updating.

    Scans existing links as values tuples straight off the through
    tables — one query per (field, batch) with the key attrs joined in
    SQL — instead of materializing comics, prefetched related objects
    and their lazily-loaded FK chains (which cost a single-row SELECT
    per credit/identifier/story-arc-number row).
    """

    @staticmethod
    def _m2m_key_value_paths(field: "ManyToManyField") -> tuple[str, ...]:
        """
        Build the values_list paths that reproduce the runtime key tuple.

        Mirrors the old per-object attribute walk: key attrs that are
        relations to named models contribute their ``name``; plain
        columns contribute their value.
        """
        target_model = field.related_model
        paths = []
        for attr in FIELD_NAME_KEY_ATTRS_MAP[field.name]:
            attr_field = target_model._meta.get_field(attr)
            related = attr_field.related_model if attr_field.is_relation else None
            if isinstance(related, type) and issubclass(
                related, NamedModel | BrowserCollectionModel
            ):
                path = f"{attr}__name"
            else:
                path = attr
            paths.append(path)
        return tuple(paths)

    def _record_removed_m2m_source_collection(
        self, field_name: str, target_pk: int, story_arc_pk: int | None
    ) -> None:
        """
        Stash the collection a comic was just removed from (m2m unlink).

        Story arcs (and folders) are browse collections linked m2m, so a comic
        leaving one must re-stamp the SOURCE arc/folder — ``TimestampUpdater``
        only re-stamps collections a *current* comic still links into. Mirrors
        the FK move capture in ``CreateComicsImporter``; the delete phase folds
        these into the force-update map. Tag-style m2ms (genres, characters, …)
        are not collections and are ignored here.
        """
        if field_name == STORY_ARC_NUMBERS_FIELD_NAME:
            model: type[BrowserCollectionModel] = StoryArc
            source_pk = story_arc_pk
        elif field_name == FOLDERS_FIELD_NAME:
            model = Folder
            source_pk = target_pk
        else:
            return
        if source_pk is not None:
            self.moved_source_collections.setdefault(model, set()).add(source_pk)

    def _add_kept_values_to_fts(
        self,
        field_name: str,
        pk_path_map: dict[int, str],
        kept_map: dict[int, set[tuple]],
        deleted_pks: set[int],
    ) -> None:
        """Record kept values for comics whose field membership changed."""
        link_m2ms = self.metadata[LINK_M2MS]
        for comic_pk, kept_values in kept_map.items():
            # Remaining proposed values get created by the link phase;
            # like deletions they change the entry, so the kept values
            # must be folded into the rebuilt FTS row.
            if comic_pk in deleted_pks or link_m2ms[pk_path_map[comic_pk]][field_name]:
                self.add_to_fts_existing(comic_pk, field_name, tuple(kept_values))

    def _query_prune_m2m_field(
        self,
        field_name: str,
        pk_path_map: dict[int, str],
        comic_pks: tuple[int, ...],
        status,
    ) -> None:
        """Prune one m2m field's existing links with a through-table scan."""
        field = cast("ManyToManyField", Comic._meta.get_field(field_name))
        through_model = get_through_model(field)
        target_rel = field.related_model._meta.model_name
        value_paths = self._m2m_key_value_paths(field)
        key_end = 2 + len(value_paths)
        extra_cols = (
            (f"{target_rel}__{STORY_ARC_FIELD_NAME}_id",)
            if field_name == STORY_ARC_NUMBERS_FIELD_NAME
            else ()
        )
        rows = through_model.objects.filter(comic_id__in=comic_pks).values_list(
            "comic_id",
            f"{target_rel}_id",
            *(f"{target_rel}__{path}" for path in value_paths),
            *extra_cols,
        )

        link_m2ms = self.metadata[LINK_M2MS]
        delete_m2ms = self.metadata[DELETE_M2MS].setdefault(field_name, set())
        kept_map: dict[int, set[tuple]] = {}
        deleted_pks: set[int] = set()
        count = 0
        for row in rows.iterator(chunk_size=IMPORTER_LINK_M2M_BATCH_SIZE):
            comic_pk = row[0]
            key_tuple = row[2:key_end]
            proposed_values = link_m2ms[pk_path_map[comic_pk]][field_name]
            if key_tuple in proposed_values:
                # Already linked correctly: remove from the action set.
                kept_map.setdefault(comic_pk, set()).add(key_tuple)
                proposed_values.discard(key_tuple)
            else:
                # Existing link the new metadata doesn't propose: delete.
                target_pk = row[1]
                delete_m2ms.add((comic_pk, target_pk))
                self._record_removed_m2m_source_collection(
                    field_name, target_pk, row[-1] if extra_cols else None
                )
                deleted_pks.add(comic_pk)
            count += 1
        status.increment_complete(count)
        self.status_controller.update(status)
        self._add_kept_values_to_fts(field_name, pk_path_map, kept_map, deleted_pks)

    def _drop_empty_m2m_entries(self, db_paths: Iterable[str]) -> None:
        """Drop emptied proposed-value sets for comics that exist in the db."""
        link_m2ms = self.metadata[LINK_M2MS]
        for path in db_paths:
            path_links = link_m2ms[path]
            for field_name in tuple(path_links):
                if not path_links[field_name]:
                    del path_links[field_name]
            if not path_links:
                del link_m2ms[path]

    def _query_prune_comic_m2m_links_batch(
        self, batch_paths: tuple[str, ...], field_names: tuple[str, ...], status
    ) -> None:
        """
        Prune one batch of comic paths, field by field.

        A field absent from a comic's LINK_M2MS means "leave its
        existing links alone", so each field's scan is restricted to
        the comics that actually propose values for it. Paths missing
        from the db (newly created comics) have nothing to prune and
        keep their proposed values for the link phase.
        """
        pk_path_map: dict[int, str] = dict(
            Comic.objects.filter(
                library=self.library, path__in=batch_paths
            ).values_list("pk", "path")
        )
        link_m2ms = self.metadata[LINK_M2MS]
        for field_name in field_names:
            comic_pks = tuple(
                pk for pk, path in pk_path_map.items() if field_name in link_m2ms[path]
            )
            if comic_pks:
                self._query_prune_m2m_field(field_name, pk_path_map, comic_pks, status)
        self._drop_empty_m2m_entries(pk_path_map.values())

    def _collect_referenced_m2m_fields(self) -> tuple[str, ...]:
        """
        Return the COMIC_M2M_FIELD_NAMES subset actually referenced.

        Most imports only touch a handful of M2M fields (credits, tags,
        characters); narrowing the scan set drops 10+ wasted queries
        per batch.
        """
        referenced: set[str] = set()
        for path_link in self.metadata[LINK_M2MS].values():
            referenced.update(path_link.keys())
        return tuple(name for name in COMIC_M2M_FIELD_NAMES if name in referenced)

    def query_prune_comic_m2m_links(self, status) -> None:
        """Prune comic m2m links that already exists or should be deleted."""
        status.subtitle = "Many to Many"
        self.status_controller.update(status)
        field_names = self._collect_referenced_m2m_fields()
        if not field_names:
            return
        paths = tuple(self.metadata[LINK_M2MS].keys())
        # Batch path__in to stay under SQLite's variable limit.
        for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
            if self.abort_event.is_set():
                return
            batch_paths = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            self._query_prune_comic_m2m_links_batch(batch_paths, field_names, status)
        delete_field_names = tuple(self.metadata[DELETE_M2MS].keys())
        for field_name in delete_field_names:
            rows = self.metadata[DELETE_M2MS][field_name]
            if not rows:
                del self.metadata[DELETE_M2MS][field_name]
        status.increment_complete(len(delete_field_names))
        self.status_controller.update(status)
