"""Update fts fields for updated foreign keys with non key search values."""

from django.db.models.expressions import Value
from django.db.models.functions.datetime import Now
from django.db.models.functions.text import Concat

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
        name_concat = GroupConcat(name_rel, distinct=True)
        if field_name == "universes":
            exp = Concat(
                GroupConcat(f"{rel}__designation", distinct=True),
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
        comicftss = (
            ComicFTS.objects.filter(**{rel: model_pks})
            .exclude(pk__in=already_updated_comicfts_pks)
            .annotate(fts_value=fts_value)
            .only(*update_fields)
        )
        for comicfts in comicftss:
            setattr(comicfts, field_name, comicfts.fts_value)  # pyright: ignore[reportAttributeAccessIssue]
            comicfts.updated_at = Now()
            update_objs.append(comicfts)

    def sync_fts_for_m2m_updates(self, already_updated_comicfts_pks: tuple[int, ...]):
        """Update fts entries for foreign keys."""
        count = 0
        field_names = tuple(self.metadata[FTS_UPDATED_M2MS].keys())

        update_fields = field_names  # tuple(sorted(model.__name__.lower() + "s" for model in models))
        update_objs = []
        for field_name in field_names:
            if self.abort_event.is_set():
                return
            self._sync_fts_for_m2m_updates_model(
                field_name, already_updated_comicfts_pks, update_fields, update_objs
            )
        if update_objs:
            ComicFTS.objects.bulk_update(update_objs, update_fields)
        count += len(update_objs)
        level = "INFO" if count else "DEBUG"
        tags = ", ".join(update_fields)
        self.log.log(
            level,
            f"Updated {count} Search Indexes for comics linked to updated tags: {tags}.",
        )
        self.metadata.pop(FTS_UPDATED_M2MS)
