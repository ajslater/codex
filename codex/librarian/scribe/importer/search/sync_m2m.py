"""Update fts fields for updated foreign keys with non key search values."""

from django.db.models.expressions import Value
from django.db.models.functions.datetime import Now
from django.db.models.functions.text import Concat
from loguru import logger

from codex.librarian.scribe.importer.const import FTS_UPDATED_M2MS
from codex.librarian.scribe.importer.finish import FinishImporter
from codex.models.comic import ComicFTS
from codex.models.functions import GroupConcat


class SearchIndexSyncManyToManyImporter(FinishImporter):
    """Update fts fields for updated foreign keys with non key search values."""

    @staticmethod
    def _to_fts_str(values):
        return ",".join(sorted(values))

    @staticmethod
    def _get_fts_m2m_concat(field_name: str):
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
                    order_by=("{rel}__designation"),
                ),
                Value(","),
                name_concat,
            )
        else:
            exp = name_concat
        return exp

    def _sync_fts_for_m2m_updates_model(
        self,
        field_name: str,
        already_updated_comicfts_pks: tuple[int, ...],
        update_fields: tuple[str, ...],
        update_objs: list[ComicFTS],
    ):
        rel = f"comic__{field_name}__in"
        fts_value = self._get_fts_m2m_concat(field_name)
        model_pks = self.metadata[FTS_UPDATED_M2MS].pop(field_name)
        self.log.debug(
            f"Preparing {len(model_pks)} search entries for {field_name} updates."
        )
        comicftss = (
            ComicFTS.objects.filter(**{rel: model_pks})
            .exclude(pk__in=already_updated_comicfts_pks)
            .annotate(fts_value=fts_value)
            .only(*update_fields)
        )
        for comicfts in comicftss:
            value = comicfts.fts_value.strip(",")  # pyright: ignore[reportAttributeAccessIssue]
            setattr(comicfts, field_name, value)
            comicfts.updated_at = Now()
            update_objs.append(comicfts)

    def sync_fts_for_m2m_updates(self, already_updated_comicfts_pks: tuple[int, ...]):
        """Update fts entries for foreign keys."""
        try:
            count = 0
            update_field_names = tuple(self.metadata.get(FTS_UPDATED_M2MS, {}).keys())
            if not update_field_names:
                return

            update_objs = []
            for field_name in update_field_names:
                if self.abort_event.is_set():
                    return
                self._sync_fts_for_m2m_updates_model(
                    field_name,
                    already_updated_comicfts_pks,
                    update_field_names,
                    update_objs,
                )
            count += len(update_objs)
            tags = ", ".join(update_field_names)
            self.log.debug(
                f"Updating {count} search index entries for comics linked to updated tags: {tags}"
            )
            if count:
                ComicFTS.objects.bulk_update(update_objs, update_field_names)
            level = "INFO" if count else "DEBUG"
            self.log.log(
                level,
                f"Updated {count} search indexes entries for comics linked to updated tags: {tags}.",
            )
        except Exception as exc:
            logger.warning(f"Syncing FTS for M2M Updates: {exc}")
        finally:
            self.metadata.pop(FTS_UPDATED_M2MS, None)
