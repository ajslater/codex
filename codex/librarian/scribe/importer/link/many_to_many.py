"""Link Comics M2M fields."""

from typing import TYPE_CHECKING

from codex.librarian.scribe.importer.const import (
    DELETE_M2MS,
    LINK_M2MS,
)
from codex.librarian.scribe.importer.link.sum import LinkSumImporter
from codex.librarian.scribe.importer.statii.link import ImporterLinkTagsStatus
from codex.librarian.status import Status
from codex.models import Comic

if TYPE_CHECKING:
    from django.db.models import ManyToManyField


class LinkManyToManyImporter(LinkSumImporter):
    """Link Comics M2M fields."""

    def link_comic_m2m_field(self, field_name, m2m_links, status: Status):
        """
        Recreate an m2m field for a set of comics.

        Since we can't bulk_update or bulk_create m2m fields use a trick.
        bulk_create() on the through table:
        https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452
        https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ManyToManyField.through
        """
        status.subtitle = field_name
        self.status_controller.update(status)
        field: ManyToManyField = Comic._meta.get_field(field_name)  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]│
        through_model = self.get_through_model(field)
        through_field_id_name = field.related_model.__name__.lower() + "_id"

        tms = []
        for comic_id, model_ids in m2m_links.items():
            for model_id in model_ids:
                args = {"comic_id": comic_id, through_field_id_name: model_id}
                tm = through_model(**args)
                tms.append(tm)

        count = len(tms)
        if count:
            update_fields = ("comic_id", through_field_id_name)
            through_model.objects.bulk_create(
                tms,
                update_conflicts=True,
                update_fields=update_fields,
                unique_fields=update_fields,
            )
            status.increment_complete(count)
            self.status_controller.update(status)
        return count

    def link_comic_m2m_fields(self):
        """Combine query and bulk link into a batch."""
        link_total = self.sum_ops(DELETE_M2MS) + self.sum_path_ops(LINK_M2MS)
        status = ImporterLinkTagsStatus(0, link_total)
        try:
            if not link_total:
                self.status_controller.finish(status)
                return link_total

            self.status_controller.start(status)
            del_total = self.delete_m2ms(status)

            # get ids for through model writing.
            all_m2m_links = self.link_prepare_m2m_links(status)

            num_links = sum(
                len(m2m_links.values()) for m2m_links in all_m2m_links.values()
            )
            status.total = num_links

            created_total = 0
            for field_name, m2m_links in all_m2m_links.items():
                if self.abort_event.is_set():
                    return created_total + del_total
                try:
                    created_total += self.link_comic_m2m_field(
                        field_name, m2m_links, status
                    )
                except Exception:
                    self.log.exception(f"Error recreating m2m field: {field_name}")
        finally:
            self.metadata.pop(LINK_M2MS, None)
            self.metadata.pop(DELETE_M2MS, None)
            self.status_controller.finish(status)
        return created_total + del_total
