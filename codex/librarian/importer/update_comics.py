"""Bulk update comic objects."""

from django.db.models import NOT_PROVIDED
from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.const import (
    BULK_UPDATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS_WITH_VALUES,
)
from codex.librarian.importer.link_comics import LinkComicsMixin
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import (
    Comic,
    Timestamp,
)


class UpdateComicsMixin(LinkComicsMixin):
    """Create comics methods."""

    def _bulk_update_comics_add_comic(self, static_data, comic, results):
        """Add one comic and stats to the bulk update list."""
        try:
            library, mds, now = static_data
            md = mds.pop(comic.path)
            self.get_comic_fk_links(md, library, comic.path)
            for field_name in BULK_UPDATE_COMIC_FIELDS_WITH_VALUES:
                value = md.get(field_name)
                if value is None:
                    default_value = Comic._meta.get_field(field_name).default
                    if default_value != NOT_PROVIDED:
                        value = default_value
                setattr(comic, field_name, value)
            comic.presave()
            comic.set_stat()
            comic.updated_at = now
            update_comics, comic_pks, comic_update_paths = results
            update_comics.append(comic)
            comic_pks.append(comic.pk)
            comic_update_paths.add(comic.path)
        except Exception:
            self.log.exception(f"Error preparing {comic} for update.")

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
        static_data = library, mds, now
        results = update_comics, comic_pks, comic_update_paths
        for comic in comics.iterator():
            self._bulk_update_comics_add_comic(static_data, comic, results)

        converted_create_paths = frozenset(set(comic_paths) - comic_update_paths)
        create_paths.update(converted_create_paths)
        count = len(converted_create_paths)
        if count:
            self.log.info(f"Converted {count} update paths to create paths.")

        self.log.debug(f"Bulk updating {len(update_comics)} comics.")
        try:
            Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
            Timestamp.touch(Timestamp.TimestampChoices.COVERS)
            count = len(update_comics)

            task = CoverRemoveTask(frozenset(comic_pks))
            self.log.debug(f"Purging covers for {len(comic_pks)} updated comics.")
            self.librarian_queue.put(task)
            if count:
                self.log.info(f"Updated {count} comics.")
        except Exception:
            self.log.exception(f"While updating {comic_update_paths}")

        return count
