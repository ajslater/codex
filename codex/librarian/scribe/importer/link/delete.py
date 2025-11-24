"""Delete stale m2ms."""

from typing import TYPE_CHECKING

from django.db.models import ManyToManyField, Q

from codex.librarian.scribe.importer.const import (
    DELETE_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
)
from codex.librarian.scribe.importer.link.prepare import LinkComicsImporterPrepare
from codex.models import Comic
from codex.models.base import BaseModel
from codex.settings import FILTER_BATCH_SIZE

if TYPE_CHECKING:
    from django.db.models.fields.related import ManyToManyRel


class LinkImporterDelete(LinkComicsImporterPrepare):
    """Delete stale m2ms."""

    @staticmethod
    def get_through_model(field: ManyToManyField) -> type[BaseModel]:
        """Get the through model for a m2m field."""
        remote_field: ManyToManyRel = field.remote_field  # pyright: ignore[reportAssignmentType],# ty: ignore[invalid-assignment]
        return remote_field.through  #  pyright: ignore[reportReturnType],# ty: ignore[invalid-return-type]

    def _delete_m2m_field_batch(
        self,
        column_name: str,
        through_model: type[BaseModel],
        batch_rows: tuple,
        comic_ids: set[int],
    ):
        del_filter = Q()
        for row in batch_rows:
            comic_id, model_id = row
            del_filter_dict = {"comic_id": comic_id, column_name: model_id}
            del_filter |= Q(**del_filter_dict)
            comic_ids.add(comic_id)

        qs = through_model.objects.filter(del_filter)
        count, _ = qs.delete()
        return count

    def _delete_m2m_fts_entries(self, field_name: str, comic_ids: set[int]):
        fts_field_name = (
            "story_arcs" if field_name == "story_arc_numbers" else field_name
        )
        for comic_id in comic_ids:
            if not self.metadata.get(FTS_UPDATE, {}).get(comic_id, {}).get(
                fts_field_name
            ) and not self.metadata.get(FTS_EXISTING_M2MS, {}).get(comic_id, {}).get(
                fts_field_name
            ):
                self.add_links_to_fts(comic_id, fts_field_name, ())

    def delete_m2m_field(self, field_name: str, delete_m2ms: dict, status):
        """Delete one comic field's m2m relations."""
        total_field_count = 0
        rows = tuple(delete_m2ms.pop(field_name, ()))
        num_rows = len(rows)
        if not num_rows:
            return total_field_count
        status.subtitle = f"Delete stale {field_name} links"
        self.status_controller.update(status)
        field: ManyToManyField = Comic._meta.get_field(field_name)  # pyright:ignore[reportAssignmentType], # ty: ignore[invalid-assignment]│
        related_model = field.related_model
        table_name = related_model._meta.db_table
        column_name = table_name.removeprefix("codex_") + "_id"
        through_model = self.get_through_model(field)
        comic_ids = set()

        start = 0
        while start < num_rows:
            end = start + FILTER_BATCH_SIZE
            batch_rows = rows[start:end]
            count = self._delete_m2m_field_batch(
                column_name, through_model, batch_rows, comic_ids
            )
            status.complete += count
            total_field_count += count
            if count:
                self.log.info(
                    f"Deleted {total_field_count}/{num_rows} stale {field_name} relations for altered comics.",
                )

            self.status_controller.update(status)
            start += FILTER_BATCH_SIZE

        self._delete_m2m_fts_entries(field_name, comic_ids)

        return total_field_count

    def delete_m2ms(self, status):
        """Delete old missing m2ms."""
        delete_m2ms = self.metadata.pop(DELETE_M2MS, {})

        del_total = 0
        for field_name in sorted(delete_m2ms.keys()):
            del_total += self.delete_m2m_field(field_name, delete_m2ms, status)
        if del_total:
            self.log.info(f"Deleted {del_total} stale relations for altered comics.")
        return del_total
