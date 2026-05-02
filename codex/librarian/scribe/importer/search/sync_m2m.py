"""Update fts fields for updated foreign keys with non key search values."""

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models.expressions import Value
from django.db.models.functions.datetime import Now
from django.db.models.functions.text import Concat
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Collection

from codex.librarian.scribe.importer.const import FTS_UPDATED_M2MS
from codex.librarian.scribe.importer.finish import FinishImporter
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat

# SQLite caps a single statement at 32,766 host parameters by
# default. ``ComicFTS`` carries ~28 columns; 500 rows x 28 cols is a
# safe ceiling that still amortizes per-statement overhead.
_FTS_BATCH_SIZE = 500


class SearchIndexSyncManyToManyImporter(FinishImporter):
    """Update fts fields for updated foreign keys with non key search values."""

    @staticmethod
    def _to_fts_str(values) -> str:
        return ",".join(sorted(values))

    @staticmethod
    def _get_fts_m2m_concat(field_name: str) -> Concat | GroupConcat:
        rel = "comic__" + field_name
        name_rel = rel + "__name"
        name_concat = GroupConcat(
            name_rel,
            order_by=name_rel,
            distinct=True,
        )
        if field_name == "universes":
            exp = Concat(
                GroupConcat(
                    f"{rel}__designation",
                    distinct=True,
                    order_by=(f"{rel}__designation"),
                ),
                Value(","),
                name_concat,
            )
        else:
            exp = name_concat
        return exp

    def _gather_m2m_field_values(
        self, already_updated_comicfts_pks: tuple[int, ...]
    ) -> dict[int, dict[str, str]]:
        """
        Collapse FTS_UPDATED_M2MS into ``{comic_pk: {field: new_value}}``.

        One comic can be touched by several m2m field updates in the
        same import (e.g. a comic linked to both a renamed tag and a
        renamed character). Building the per-comic edit set here means
        each row is fetched and rewritten exactly once — the previous
        ``update_objs.append`` pattern produced one ``ComicFTS``
        instance per (comic, field) pair, which ``bulk_update`` then
        overwrote unpredictably when the same pk appeared twice.
        """
        per_comic: dict[int, dict[str, str]] = {}
        # ``FTS_UPDATED_M2MS`` is only populated when the link phase
        # actually saw m2m row deletions/insertions; an import that
        # only creates new comics never sets it. ``.get`` so the
        # caller's "every post-phase runs unconditionally" model
        # doesn't surface a KeyError here.
        field_names = tuple(self.metadata.get(FTS_UPDATED_M2MS, {}).keys())
        for field_name in field_names:
            if self.abort_event.is_set():
                return per_comic
            rel = f"comic__{field_name}__in"
            fts_value = self._get_fts_m2m_concat(field_name)
            model_pks = self.metadata[FTS_UPDATED_M2MS].pop(field_name)
            self.log.debug(
                f"Preparing {len(model_pks)} search entries for {field_name} updates."
            )
            rows = (
                ComicFTS.objects.filter(**{rel: model_pks})
                .exclude(pk__in=already_updated_comicfts_pks)
                .annotate(fts_value=fts_value)
                .values_list("pk", "fts_value")
            )
            for pk, raw_value in rows:
                value = (raw_value or "").strip(",")
                per_comic.setdefault(pk, {})[field_name] = value
        return per_comic

    @staticmethod
    def _apply_field_updates(
        comicfts: ComicFTS, field_updates: dict[str, str]
    ) -> ComicFTS:
        for field_name, value in field_updates.items():
            setattr(comicfts, field_name, value)
        comicfts.updated_at = Now()
        return comicfts

    def _delete_then_create_comicfts(self, comicftss: list[ComicFTS]) -> None:
        """
        Replace ComicFTS rows for ``comicftss`` via delete + bulk_create.

        FTS5 virtual tables don't accept ``UPDATE … SET col = CASE WHEN``
        cheaply (parser cost grows in rows x cols and every UPDATE is
        an internal delete-then-insert at the segment level anyway), so
        an explicit delete-then-bulk_create cuts wall time roughly 1.5-
        3x on production-shaped workloads. See
        ``tests/perf/bench_fts_sync.py`` for the supporting numbers.

        ``transaction.atomic`` makes the swap all-or-nothing — an
        interrupted run leaves the original row intact rather than a
        comic with no FTS row.
        """
        pks = [c.comic_id for c in comicftss]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        with transaction.atomic():
            for start in range(0, len(pks), _FTS_BATCH_SIZE):
                chunk = pks[start : start + _FTS_BATCH_SIZE]
                ComicFTS.objects.filter(pk__in=chunk).delete()
            ComicFTS.objects.bulk_create(comicftss, batch_size=_FTS_BATCH_SIZE)

    def _build_replacement_objs(
        self, per_comic: dict[int, dict[str, str]]
    ) -> list[ComicFTS]:
        """Fetch full rows for every affected comic and apply the edits."""
        if not per_comic:
            return []
        pks: Collection[int] = tuple(per_comic.keys())
        existing = list(ComicFTS.objects.filter(pk__in=pks))
        return [self._apply_field_updates(c, per_comic[c.comic_id]) for c in existing]  # pyright: ignore[reportAttributeAccessIssue]

    def sync_fts_for_m2m_updates(
        self, already_updated_comicfts_pks: tuple[int, ...]
    ) -> None:
        """Update fts entries for foreign keys."""
        try:
            per_comic = self._gather_m2m_field_values(already_updated_comicfts_pks)
            if self.abort_event.is_set():
                return
            tags = ", ".join(sorted({f for d in per_comic.values() for f in d}))
            count = len(per_comic)
            self.log.debug(
                f"Updating {count} search index entries for comics linked to updated tags: {tags}"
            )
            if count:
                comicftss = self._build_replacement_objs(per_comic)
                self._delete_then_create_comicfts(comicftss)
            level = "INFO" if count else "DEBUG"
            self.log.log(
                level,
                f"Updated {count} search indexes entries for comics linked to updated tags: {tags}.",
            )
        except Exception as exc:
            logger.warning(f"Syncing FTS for M2M Updates: {exc}")
            logger.exception(exc)
        finally:
            self.metadata.pop(FTS_UPDATED_M2MS, None)
