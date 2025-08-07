"""Prepare links with database objects."""

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from django.db.models.query import Q

from codex.librarian.scribe.importer.const import (
    FIELD_NAME_KEYS_REL_MAP,
    FOLDERS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    LINK_M2MS,
    NON_FTS_FIELDS,
)
from codex.librarian.scribe.importer.link.const import COMPLEX_MODEL_FIELD_NAMES
from codex.librarian.scribe.importer.link.covers import (
    LinkCoversImporter,
)
from codex.models import Comic
from codex.util import flatten

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class LinkComicsImporterPrepare(LinkCoversImporter):
    """Prepare links with database objects."""

    @staticmethod
    def _get_link_folders_filter(_field_name, values_set):
        """Get the ids of all folders to link."""
        folder_paths = frozenset(flatten(values_set))
        return Q(path__in=folder_paths)

    @staticmethod
    def _get_link_complex_model_filter(field_name, values_set):
        """Get the ids of all dict style objects to link."""
        rels = FIELD_NAME_KEYS_REL_MAP[field_name]
        dict_filter = Q()
        for values in values_set:
            rel_complex = dict(zip(rels, values, strict=False))
            dict_filter |= Q(**rel_complex)
        return dict_filter

    def _add_complex_link_to_fts(
        self, comic_pk: int, field_name: str, values: frozenset
    ):
        if field_name == IDENTIFIERS_FIELD_NAME:
            # sources extracton must come before identifiers is minified
            # but now identifiers is not indexed at all, yet sources are.
            sources = tuple(sorted({subvalues[0] for subvalues in values}))
            self.add_links_to_fts(comic_pk, "sources", sources)

        if field_name in NON_FTS_FIELDS:
            return

        field_name, fts_values = self.minify_complex_link_to_fts_tuple(
            field_name, values
        )
        self.add_links_to_fts(comic_pk, field_name, fts_values)

    def _link_prepare_complex_m2ms(
        self,
        all_m2m_links: dict,
        md: dict,
        comic_pk: int,
        field_name: str,
        link_filter_method: Callable,
    ):
        """Prepare special m2m for linking."""
        values = md.pop(field_name, None)
        if not values:
            return
        self._add_complex_link_to_fts(comic_pk, field_name, values)
        model: type[BaseModel] = Comic._meta.get_field(field_name).related_model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]│
        m2m_filter = link_filter_method(field_name, values)
        pks = model.objects.filter(m2m_filter).values_list("pk", flat=True).distinct()
        if result := tuple(pks):
            if field_name not in all_m2m_links:
                all_m2m_links[field_name] = {}
            all_m2m_links[field_name][comic_pk] = result

    def _link_prepare_named_m2ms(
        self,
        all_m2m_links: dict,
        comic_pk: int,
        field_name: str,
        names: tuple[str, ...] | frozenset[str],
    ):
        """Set the ids of all named m2m fields into the comic dict."""
        model = Comic._meta.get_field(field_name).related_model
        if model is None:
            self.log.error(f"No related class found for Comic.{field_name}")
            return
        self.add_links_to_fts(comic_pk, field_name, tuple(names))
        names = frozenset(name[0] for name in names)
        pks = (
            model.objects.filter(name__in=names).values_list("pk", flat=True).distinct()
        )
        if result := tuple(pks):
            if field_name not in all_m2m_links:
                all_m2m_links[field_name] = {}
            all_m2m_links[field_name][comic_pk] = result

    def link_prepare_m2m_links(self, status) -> Mapping:
        """Get the complete m2m field data to create."""
        status.subtitle = "Preparing..."
        self.status_controller.update(status)
        all_m2m_links = {}
        comic_paths = tuple(self.metadata.get(LINK_M2MS, {}).keys())
        if not comic_paths:
            return all_m2m_links

        comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
        for comic_pk, comic_path in comics:
            md = self.metadata[LINK_M2MS][comic_path]
            self._link_prepare_complex_m2ms(
                all_m2m_links,
                md,
                comic_pk,
                FOLDERS_FIELD_NAME,
                self._get_link_folders_filter,
            )
            for field_name in COMPLEX_MODEL_FIELD_NAMES:
                self._link_prepare_complex_m2ms(
                    all_m2m_links,
                    md,
                    comic_pk,
                    field_name,
                    self._get_link_complex_model_filter,
                )
            for field, names in md.items():
                self._link_prepare_named_m2ms(all_m2m_links, comic_pk, field, names)
        self.metadata.pop(LINK_M2MS, None)
        return all_m2m_links
