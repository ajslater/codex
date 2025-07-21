"""Create Custom Covers."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.functions.datetime import Now

from codex.librarian.scribe.importer.const import (
    CLASS_CUSTOM_COVER_GROUP_MAP,
    CREATE_COVERS,
    CUSTOM_COVER_UPDATE_FIELDS,
    LINK_COVER_PKS,
    UPDATE_COVERS,
)
from codex.librarian.scribe.importer.create.comics import CreateComicsImporter
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateCoversStatus,
    ImporterUpdateCoversStatus,
)
from codex.librarian.scribe.importer.statii.link import ImporterLinkCoversStatus
from codex.models import CustomCover


class CreateCoversImporter(CreateComicsImporter):
    """Create Custom Covers."""

    @staticmethod
    def add_custom_cover_to_group(group_class, obj):
        """If a custom cover exists for this group, add it."""
        group = CLASS_CUSTOM_COVER_GROUP_MAP.get(group_class)
        if not group:
            # Normal, volume doesn't link to covers
            return
        try:
            cover = CustomCover.objects.filter(group=group, sort_name=obj.sort_name)[0]
            obj.custom_cover = cover
        except (IndexError, ObjectDoesNotExist):
            pass

    def update_custom_covers(self):
        """Update Custom Covers."""
        count = 0
        status = ImporterUpdateCoversStatus(0)
        try:
            update_covers_qs = self.metadata.pop(UPDATE_COVERS, None)
            if not update_covers_qs:
                self.status_controller.finish(status)
                return count
            update_covers_count = update_covers_qs.count()
            if not update_covers_count:
                self.status_controller.finish(status)
                return count
            status.total = update_covers_count
            self.status_controller.start(status)

            update_covers = []
            for cover in update_covers_qs.only(*CUSTOM_COVER_UPDATE_FIELDS):
                cover.updated_at = Now()
                cover.presave()
                update_covers.append(cover)

            if update_covers:
                CustomCover.objects.bulk_update(
                    update_covers, CUSTOM_COVER_UPDATE_FIELDS
                )
                update_cover_pks = update_covers_qs.values_list("pk", flat=True)
                if LINK_COVER_PKS not in self.metadata:
                    self.metadata[LINK_COVER_PKS] = set()
                self.metadata[LINK_COVER_PKS].update(update_cover_pks)
                self.remove_covers(update_cover_pks, custom=True)
                count = len(update_covers)
                if status:
                    status.increment_complete(count)

                link_covers_status = ImporterLinkCoversStatus(
                    0,
                    len(self.metadata[LINK_COVER_PKS]),
                )
                self.status_controller.update(link_covers_status, notify=False)
        finally:
            self.status_controller.finish(status)
        return count

    def create_custom_covers(self):
        """Create Custom Covers."""
        count = 0
        create_cover_paths = self.metadata.pop(CREATE_COVERS, ())
        num_create_cover_paths = len(create_cover_paths)
        status = ImporterCreateCoversStatus(0, num_create_cover_paths)
        try:
            if not num_create_cover_paths:
                self.status_controller.finish(status)
                return count

            self.status_controller.start(status)

            create_covers = []
            for path in create_cover_paths:
                cover = CustomCover(library=self.library, path=path)
                cover.presave()
                create_covers.append(cover)

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
                    status.increment_complete(count)

                link_covers_status = ImporterLinkCoversStatus(
                    0, len(self.metadata[LINK_COVER_PKS])
                )
                self.status_controller.update(link_covers_status, notify=False)

        finally:
            self.status_controller.finish(status)
        return count
