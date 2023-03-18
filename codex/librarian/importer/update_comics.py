"""Bulk update comic objects."""

from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.link_comics import LinkComicsMixin
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

    def _update_comics(
        self, library, comic_paths: set, mds, count
    ) -> tuple[int, frozenset, list]:
        """Bulk update comics."""
        if not comic_paths:
            return 0, frozenset(), []

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
            except Exception as exc:
                self.log.error(f"Error preparing {comic} for update.")
                self.log.exception(exc)
        self.log.info(
            f"Prepared {len(comic_paths)} comics for update in library {library.path}."
        )

        converted_create_paths = frozenset(comic_paths - comic_update_paths)
        self.log.info(
            f"Converted {len(converted_create_paths)} update paths to create paths."
        )

        self.log.debug(f"Bulk updating {len(update_comics)} comics.")
        try:
            count += Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)

            task = CoverRemoveTask(frozenset(comic_pks))
            self.log.debug(f"Purging covers for {len(comic_pks)} updated comics.")
            self.librarian_queue.put(task)
        except Exception as exc:
            self.log.error(exc)
            self.log.error("While updating", comic_update_paths)

        if count:
            Timestamp.touch(Timestamp.COVERS)

        return count, converted_create_paths, comic_pks

    def bulk_update_comics(
        self, library, update_paths, count, _total, create_paths, all_bulk_mds
    ):
        """Bulk update comics, and move nonextant comics into create job.."""
        # TODO try to simplify
        update_count, converted_create_paths, comic_pks = self._update_comics(
            library, update_paths, all_bulk_mds, count
        )
        create_paths.update(converted_create_paths)
        return update_count
