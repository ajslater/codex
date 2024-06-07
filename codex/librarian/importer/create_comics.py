"""Bulk update and create comic objects and bulk update m2m fields."""

from django.db.models import NOT_PROVIDED
from django.db.models.functions import Now

from codex.librarian.importer.const import (
    BULK_CREATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS_WITH_VALUES,
    MDS,
)
from codex.librarian.importer.link_comics import LinkComicsImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Comic,
)
from codex.status import Status


class CreateComicsImporter(LinkComicsImporter):
    """Create comics methods."""

    def _bulk_update_comics_add_comic(self, comic, results):
        """Add one comic and stats to the bulk update list."""
        try:
            md = self.metadata[MDS].pop(comic.path)
            self.get_comic_fk_links(md, comic.path)
            for field_name in BULK_UPDATE_COMIC_FIELDS_WITH_VALUES:
                value = md.get(field_name)
                if value is None:
                    default_value = Comic._meta.get_field(field_name).default
                    if default_value != NOT_PROVIDED:
                        value = default_value
                setattr(comic, field_name, value)
            comic.presave()
            comic.updated_at = Now()
            update_comics, comic_pks, comic_update_paths = results
            update_comics.append(comic)
            comic_pks.append(comic.pk)
            comic_update_paths.add(comic.path)
        except Exception:
            self.log.exception(f"Error preparing {comic} for update.")

    def bulk_update_comics(self):
        """Bulk update comics, and move nonextant comics into create job.."""
        num_comics = len(self.task.files_modified)
        if not num_comics:
            return num_comics

        self.log.debug(
            f"Preparing {num_comics} comics for update in library {self.library.path}."
        )
        status = Status(ImportStatusTypes.FILES_MODIFIED, 0, num_comics)
        self.status_controller.start(status, notify=False)
        # Get existing comics to update
        comics = Comic.objects.filter(
            library=self.library, path__in=self.task.files_modified
        ).only(*BULK_UPDATE_COMIC_FIELDS)

        # set attributes for each comic
        update_comics = []
        comic_pks = []
        comic_update_paths = set()
        results = update_comics, comic_pks, comic_update_paths
        for comic in comics.iterator():
            self._bulk_update_comics_add_comic(comic, results)

        converted_create_paths = frozenset(
            set(self.task.files_modified) - comic_update_paths
        )
        self.task.files_created |= converted_create_paths
        count = len(converted_create_paths)
        if count:
            self.log.info(f"Converted {count} update paths to create paths.")

        self.log.debug(f"Bulk updating {len(update_comics)} comics.")
        try:
            Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
            count = len(update_comics)

            self._remove_covers(comic_pks, False)  # type: ignore
            self.log.debug(f"Purging covers for {len(comic_pks)} updated comics.")
            if count:
                self.log.info(f"Updated {count} comics.")
        except Exception:
            self.log.exception(f"While updating {comic_update_paths}")

        self.task.files_modified = frozenset()

        self.status_controller.finish(status)
        return count

    def bulk_create_comics(self):
        """Bulk create comics."""
        num_comics = len(self.task.files_created)
        if not num_comics:
            return num_comics
        # prepare create comics
        self.log.debug(
            f"Preparing {num_comics} comics for creation in library {self.library.path}."
        )
        status = Status(ImportStatusTypes.FILES_CREATED, 0, num_comics)
        self.status_controller.start(status, notify=False)

        create_comics = []
        for path in sorted(self.task.files_created):
            try:
                md = self.metadata[MDS].pop(path, {})
                self.get_comic_fk_links(md, path)
                comic = Comic(**md, library=self.library)
                comic.presave()
                create_comics.append(comic)
            except KeyError:
                self.log.warning(f"No comic metadata for {path}")
            except Exception:
                self.log.exception(f"Error preparing {path} for create.")
        self.task.files_created = frozenset()
        self.metadata.pop(MDS)

        num_comics = len(create_comics)
        count = 0
        if num_comics:
            self.log.debug(f"Bulk creating {num_comics} comics...")
            try:
                Comic.objects.bulk_create(
                    create_comics,
                    update_conflicts=True,
                    update_fields=BULK_CREATE_COMIC_FIELDS,
                    unique_fields=Comic._meta.unique_together[0],  # type: ignore
                )
                count = len(create_comics)
                if count:
                    self.log.info(f"Created {count} comics.")
            except Exception:
                self.log.exception(f"While creating {num_comics} comics")

        self.changed += count
        self.status_controller.finish(status)
        return count
