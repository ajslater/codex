"""Delete stale m2ms."""

from typing import TYPE_CHECKING

from django.db.models import ManyToManyField, Q

from codex.librarian.importer.const import DELETE_M2MS
from codex.librarian.importer.link.prepare import LinkComicsImporterPrepare
from codex.models import Comic
from codex.models.base import BaseModel

if TYPE_CHECKING:
    from django.db.models.fields.related import ManyToManyRel


class LinkImporterDelete(LinkComicsImporterPrepare):
    """Delete stale m2ms."""

    @staticmethod
    def get_through_model(field: ManyToManyField) -> type[BaseModel]:
        """Get the through model for a m2m field."""
        remote_field: ManyToManyRel = field.remote_field  # pyright: ignore[reportAssignmentType]
        return remote_field.through  #  pyright: ignore[reportReturnType]

    def _delete_m2m_field(self, field_name: str, rows: tuple, status):
        """Delete one comic field's m2m relations."""
        if not rows:
            return 0
        field: ManyToManyField = Comic._meta.get_field(field_name)  # pyright:ignore[reportAssignmentType]
        related_model = field.related_model
        status.subtitle = "Delete stale {field_name} links"
        self.status_controller.update(status)
        table_name = related_model._meta.db_table
        column_name = table_name.removeprefix("codex_") + "_id"

        through_model = self.get_through_model(field)
        del_filter = Q()
        for row in rows:
            comic_id, model_id = row
            del_filter_dict = {"comic_id": comic_id, column_name: model_id}
            del_filter |= Q(**del_filter_dict)
        count, _ = through_model.objects.filter(del_filter).delete()
        if count:
            self.log.info(
                f"Deleted {count} stale {field_name} relations for altered comics.",
            )
        status.complete += count
        self.status_controller.update(status)
        return count

    def delete_m2ms(self, status):
        """Delete old missing m2ms."""
        delete_m2ms = self.metadata.pop(DELETE_M2MS, {})

        del_total = 0
        for field_name, rows in delete_m2ms.items():
            del_total += self._delete_m2m_field(field_name, rows, status)
        if del_total:
            self.log.info(f"Deleted {del_total} stale relations for altered comics.")
        return del_total
