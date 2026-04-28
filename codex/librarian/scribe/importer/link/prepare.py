"""Prepare links with database objects."""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from django.db.models.query_utils import Q

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
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE

if TYPE_CHECKING:
    from codex.models.base import BaseModel

# Q-OR chain length cap for multi-column M2M lookups (Credits,
# StoryArcNumbers, Identifiers). SQLite's expression-tree depth limits
# kick in long before the variable cap on chained-OR queries; 500
# leaves the planner well-behaved without sacrificing per-batch yield.
_M2M_OR_CHAIN_CAP = 500
# Field types that flow through the existing _add_complex_link_to_fts
# path. Everything else is treated as a "named" M2M and goes through
# add_links_to_fts directly.
_COMPLEX_FIELDS_FOR_FTS = frozenset((FOLDERS_FIELD_NAME, *COMPLEX_MODEL_FIELD_NAMES))


class LinkComicsImporterPrepare(LinkCoversImporter):
    """Prepare links with database objects."""

    def _add_complex_link_to_fts(
        self, comic_pk: int, field_name: str, values: frozenset
    ) -> None:
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

    @staticmethod
    def _collect_m2m_keys_per_field(
        link_m2ms: Mapping,
    ) -> dict[str, set[tuple]]:
        """
        Collect every key tuple referenced by any comic, per M2M field.

        Walked once at the top of the link phase so the per-comic loop
        below can resolve names→pks via dict lookup instead of firing
        one SELECT per ``(comic, field)`` pair.
        """
        per_field: dict[str, set[tuple]] = {}
        for md in link_m2ms.values():
            for field_name, value_tuples in md.items():
                if not value_tuples:
                    continue
                per_field.setdefault(field_name, set()).update(value_tuples)
        return per_field

    @staticmethod
    def _build_pk_map_single_key(
        model: type["BaseModel"], rel: str, key_tuples: set[tuple]
    ) -> dict[tuple, int]:
        """Resolve key tuples for a single-column model via batched IN."""
        pk_map: dict[tuple, int] = {}
        # IN clause batched against SQLite's 32766-variable cap.
        values = sorted({tup[0] for tup in key_tuples if tup})
        for start in range(0, len(values), IMPORTER_LINK_FK_BATCH_SIZE):
            batch = values[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            rows = model.objects.filter(**{f"{rel}__in": batch}).values_list("pk", rel)
            for pk, key in rows:
                pk_map[(key,)] = pk
        return pk_map

    @staticmethod
    def _build_pk_map_multi_key(
        model: type["BaseModel"], rels: tuple[str, ...], key_tuples: set[tuple]
    ) -> dict[tuple, int]:
        """Resolve key tuples for a multi-column model via batched Q-OR."""
        pk_map: dict[tuple, int] = {}
        # Q-OR chain batched at a planner-friendly cap.
        tuples = sorted(key_tuples)
        for start in range(0, len(tuples), _M2M_OR_CHAIN_CAP):
            batch = tuples[start : start + _M2M_OR_CHAIN_CAP]
            or_q = Q()
            for tup in batch:
                or_q |= Q(**dict(zip(rels, tup, strict=False)))
            rows = model.objects.filter(or_q).values_list("pk", *rels)
            for row in rows:
                pk_map[tuple(row[1:])] = row[0]
        return pk_map

    def _build_field_pk_map(
        self, field_name: str, key_tuples: set[tuple]
    ) -> dict[tuple, int]:
        """
        Issue batched query/queries for one M2M field.

        Returns ``{key_tuple: pk}`` covering every key the import touches
        for ``field_name``. One round-trip per ``IMPORTER_LINK_FK_BATCH_SIZE``
        chunk for single-column models, one per ``_M2M_OR_CHAIN_CAP``
        chunk for multi-column complex models.
        """
        if not key_tuples:
            return {}
        field = Comic._meta.get_field(field_name)
        model: type[BaseModel] = field.related_model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        rels = FIELD_NAME_KEYS_REL_MAP[field_name]
        if len(rels) == 1:
            return self._build_pk_map_single_key(model, rels[0], key_tuples)
        return self._build_pk_map_multi_key(model, rels, key_tuples)

    def _build_m2m_pk_maps(
        self, per_field: Mapping[str, set[tuple]]
    ) -> dict[str, dict[tuple, int]]:
        """Build ``{field_name: {key_tuple: pk}}`` from one query per field."""
        return {
            field_name: self._build_field_pk_map(field_name, key_tuples)
            for field_name, key_tuples in per_field.items()
        }

    def _add_field_to_fts(
        self, comic_pk: int, field_name: str, value_tuples: Iterable[tuple]
    ) -> None:
        """Mirror the existing FTS-update side-effect per field type."""
        if field_name in _COMPLEX_FIELDS_FOR_FTS:
            self._add_complex_link_to_fts(comic_pk, field_name, frozenset(value_tuples))
        else:
            # Named M2Ms: pass tuple-of-(name,) tuples through; the FTS
            # helper flattens internally.
            self.add_links_to_fts(comic_pk, field_name, tuple(value_tuples))

    @staticmethod
    def _resolve_pks(
        value_tuples: Iterable[tuple], field_pk_map: Mapping[tuple, int]
    ) -> tuple[int, ...]:
        """Resolve value tuples to pks via the prebuilt map."""
        return tuple(
            pk for tup in value_tuples if (pk := field_pk_map.get(tup)) is not None
        )

    def link_prepare_m2m_links(self, status) -> Mapping:
        """
        Get the complete m2m field data to create.

        Three-phase pass over LINK_M2MS:

        1. **Collect**: walk every comic's M2M dict once, grouping
           the referenced key tuples by field name.
        2. **Resolve**: one batched SELECT per M2M field builds a
           ``{key_tuple: pk}`` map.
        3. **Stitch**: walk LINK_M2MS again, resolving each comic's
           per-field key tuples to pk tuples via dict lookup.

        Replaces a previous shape that fired one SELECT per
        ``(comic, M2M field)`` pair — for a 600k-comic import that
        was ~6.6M small SELECTs dominated by round-trip overhead.
        """
        status.subtitle = "Preparing..."
        self.status_controller.update(status)
        all_m2m_links: dict[str, dict[int, tuple[int, ...]]] = {}
        link_m2ms = self.metadata.get(LINK_M2MS, {})
        if not link_m2ms:
            return all_m2m_links

        # Phase 1+2: collect every (field, key_tuple) once and resolve
        # to pks per field via a single batched query each.
        per_field = self._collect_m2m_keys_per_field(link_m2ms)
        pk_maps = self._build_m2m_pk_maps(per_field)

        # Phase 3: per-comic stitch — pure dict lookups, no SQL.
        comic_paths = tuple(link_m2ms.keys())
        comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
        for comic_pk, comic_path in comics:
            md = link_m2ms.get(comic_path, {})
            for field_name, value_tuples in md.items():
                if not value_tuples:
                    continue
                self._add_field_to_fts(comic_pk, field_name, value_tuples)
                pks = self._resolve_pks(value_tuples, pk_maps.get(field_name, {}))
                if pks:
                    all_m2m_links.setdefault(field_name, {})[comic_pk] = pks

        self.metadata.pop(LINK_M2MS, None)
        return all_m2m_links
