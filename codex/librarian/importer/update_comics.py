"""Bulk update comic objects."""

from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.link_comics import LinkComicsMixin
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import (
    Comic,
    Timestamp,
)

_EXCLUDEBULK_UPDATE_COMIC_FIELDS = {
    "created_at",
    "searchresult",
    "id",
    "bookmark",
}
BULK_UPDATE_COMIC_FIELDS = []
for field in Comic._meta.get_fields():
    if (not field.many_to_many) and (
        field.name not in _EXCLUDEBULK_UPDATE_COMIC_FIELDS
    ):
        BULK_UPDATE_COMIC_FIELDS.append(field.name)


class UpdateComicsMixin(LinkComicsMixin):
    """Create comics methods."""

    @status_notify(status_type=ImportStatusTypes.FILES_MODIFIED, updates=False)
    def bulk_update_comics(self, comic_paths, library, create_paths, mds, **kwargs):
        """Bulk update comics, and move nonextant comics into create job.."""
        count = 0
        if not comic_paths:
            return count

        self.log.debug(
            f"Preparing {len(comic_paths)} comics for update in library {library.path}."
        )
        # Get existing comics to update
        comics = Comic.objects.filter(library=library, path__in=comic_paths).only(
            *BULK_UPDATE_COMIC_FIELDS
        )

        # set attributes for each comic
        update_comics = []
        now = Now()
        comic_pks = []
        comic_update_paths = set()
        for comic in comics.iterator():
            try:
                md = mds.pop(comic.path)
                self._link_comic_fks(md, library, comic.path)
                for field_name, value in md.items():
                    setattr(comic, field_name, value)
                comic.presave()
                comic.set_stat()
                comic.updated_at = now
                update_comics.append(comic)
                comic_pks.append(comic.pk)
                comic_update_paths.add(comic.path)
            except Exception:
                self.log.exception(f"Error preparing {comic} for update.")

        converted_create_paths = frozenset(set(comic_paths) - comic_update_paths)
        create_paths.update(converted_create_paths)
        self.log.info(
            f"Converted {len(converted_create_paths)} update paths to create paths."
        )

        self.log.debug(f"Bulk updating {len(update_comics)} comics.")
        try:
            Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
            Timestamp.touch(Timestamp.TimestampChoices.COVERS)
            count = len(update_comics)

            task = CoverRemoveTask(frozenset(comic_pks))
            self.log.debug(f"Purging covers for {len(comic_pks)} updated comics.")
            self.librarian_queue.put(task)
            self.log.info(f"Updated {count} comics.")
        except Exception:
            self.log.exception(f"While updating {comic_update_paths}")

        return count
