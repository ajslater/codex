"""Create Custom Covers."""

from django.db.models.functions.datetime import Now

from codex.librarian.importer.const import (
    COVERS_CREATE,
    COVERS_UPDATE,
    CUSTOM_COVER_UPDATE_FIELDS,
    LINK_COVER_PKS,
)
from codex.librarian.importer.create_comics import CreateComicsImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    CustomCover,
)
from codex.status import Status


class CreateCoversImporter(CreateComicsImporter):
    """Create Custom Covers."""

    def update_custom_covers(self, status=None):
        """Update Custom Covers."""
        update_covers_qs = self.metadata.pop(COVERS_UPDATE, None)
        if not update_covers_qs:
            return
        update_covers_count = update_covers_qs.count()
        if not update_covers_count:
            return
        status = Status(ImportStatusTypes.COVERS_MODIFIED, 0, update_covers_count)
        self.status_controller.start(status)

        update_covers = []
        for cover in update_covers_qs.only(*CUSTOM_COVER_UPDATE_FIELDS):
            cover.updated_at = Now()
            cover.presave()
            update_covers.append(cover)

        count = 0
        if update_covers:
            CustomCover.objects.bulk_update(update_covers, CUSTOM_COVER_UPDATE_FIELDS)
            update_cover_pks = update_covers_qs.values_list("pk", flat=True)
            if LINK_COVER_PKS not in self.metadata:
                self.metadata[LINK_COVER_PKS] = set()
            self.metadata[LINK_COVER_PKS].update(update_cover_pks)
            self._remove_covers(update_cover_pks, custom=True)  # type: ignore
            count = len(update_covers)
            if status:
                status.add_complete(count)

            link_covers_status = Status(
                ImportStatusTypes.COVERS_LINK, 0, len(self.metadata[LINK_COVER_PKS])
            )
            self.status_controller.update(link_covers_status, notify=False)

        self.changed += count
        self.status_controller.finish(status)

    def create_custom_covers(self, status=None):
        """Create Custom Covers."""
        create_cover_paths = self.metadata.pop(COVERS_CREATE, ())
        num_create_cover_paths = len(create_cover_paths)
        if not num_create_cover_paths:
            return
        status = Status(ImportStatusTypes.COVERS_MODIFIED, 0, num_create_cover_paths)
        self.status_controller.start(status)

        create_covers = []
        for path in create_cover_paths:
            cover = CustomCover(library=self.library, path=path)
            cover.presave()
            create_covers.append(cover)

        count = 0
        if create_covers:
            objs = CustomCover.objects.bulk_create(
                create_covers,
                update_conflicts=True,
                update_fields=("path", "stat"),
                unique_fields=CustomCover._meta.unique_together[0],
            )
            created_pks = frozenset(obj.pk for obj in objs)
            if LINK_COVER_PKS not in self.metadata:
                self.metadata[LINK_COVER_PKS] = set()
            self.metadata[LINK_COVER_PKS].update(created_pks)
            count = len(created_pks)
            if status:
                status.add_complete(count)

            link_covers_status = Status(
                ImportStatusTypes.COVERS_LINK, 0, len(self.metadata[LINK_COVER_PKS])
            )
            self.status_controller.update(link_covers_status, notify=False)

        self.changed += count
        self.status_controller.finish(status)
