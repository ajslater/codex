"""Bulk update and create comic objects and bulk update m2m fields."""

from django.db.models import NOT_PROVIDED
from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    BULK_CREATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS,
    CREATE_COMICS,
    FTS_CREATE,
    FTS_UPDATE,
    LINK_FKS,
    NON_FTS_FIELDS,
    PATH_FIELD_NAME,
    UPDATE_COMICS,
)
from codex.librarian.scribe.importer.create.link_fks import (
    CreateForeignKeyLinksImporter,
)
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateComicsStatus,
    ImporterUpdateComicsStatus,
)
from codex.models import Comic


class CreateComicsImporter(CreateForeignKeyLinksImporter):
    """Create comics methods."""

    def _populate_fts_attribute_values(self, key: str, sub_key: str | int, md):
        if sub_key not in self.metadata[key]:
            self.metadata[key][sub_key] = {}
        for field_name, value in md.items():
            if field_name not in NON_FTS_FIELDS:
                self.metadata[key][sub_key][field_name] = (value,)

    def _update_comic_values(self, comic: Comic, update_comics: list, comic_pks: list):
        md = self.metadata[UPDATE_COMICS].pop(comic.pk, {})
        for field_name, value in md.items():
            setattr(comic, field_name, value)

        self._populate_fts_attribute_values(FTS_UPDATE, comic.pk, md)
        link_md = self.get_comic_fk_links(comic.pk, comic.path)
        for field_name, value in link_md.items():
            set_value = value
            if set_value is None:
                default_value = Comic._meta.get_field(field_name).default
                if default_value != NOT_PROVIDED:
                    set_value = default_value
            setattr(comic, field_name, set_value)
        comic.presave()
        comic.updated_at = Now()
        update_comics.append(comic)
        comic_pks.append(comic.pk)

    def update_comics(self):
        """Bulk update comics, and move nonextant comics into create job.."""
        count = 0
        pks = tuple(sorted(self.metadata[UPDATE_COMICS].keys()))
        num_comics = len(pks)
        status = ImporterUpdateComicsStatus(None, num_comics)
        try:
            if not num_comics:
                self.metadata.pop(UPDATE_COMICS)
                self.status_controller.finish(status)
                return count

            self.log.debug(
                f"Preparing {num_comics} comics for update in library {self.library.path}."
            )
            self.status_controller.start(status)
            self.metadata[FTS_UPDATE] = {}
            # Get existing comics to update
            comics = Comic.objects.filter(library=self.library, pk__in=pks).only(
                PATH_FIELD_NAME, *BULK_UPDATE_COMIC_FIELDS
            )

            # set attributes for each comic
            update_comics = []
            comic_pks = []
            for comic in comics:
                if self.abort_event.is_set():
                    return count
                try:
                    self._update_comic_values(comic, update_comics, comic_pks)
                except Exception:
                    self.log.exception(f"Error preparing {comic} for update.")
            self.metadata.pop(UPDATE_COMICS)

            count = len(update_comics)
            if count:
                self.log.debug(f"Bulk updating {len(update_comics)} comics.")
                Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
                if comic_pks:
                    self.log.debug(
                        f"Purging covers for {len(comic_pks)} updated comics."
                    )
                    self.remove_covers(comic_pks, custom=False)
        except Exception:
            self.log.exception(f"While updating comics: {pks}")
        finally:
            self.status_controller.finish(status)
        return count

    def _bulk_create_comic(self, path: str, create_comics: list[Comic]):
        md = self.metadata[CREATE_COMICS].pop(path, {})
        self._populate_fts_attribute_values(FTS_CREATE, path, md)
        link_md = self.get_comic_fk_links(path, path)
        md.update(link_md)
        if not md:
            return
        comic = Comic(**md, library=self.library)
        comic.presave()
        create_comics.append(comic)

    def create_comics(self):
        """Bulk create comics."""
        count = 0
        paths = tuple(sorted(self.metadata[CREATE_COMICS].keys()))
        num_comics = len(paths)
        status = ImporterCreateComicsStatus(None, num_comics)
        try:
            if not num_comics:
                self.metadata.pop(CREATE_COMICS)
                self.metadata.pop(LINK_FKS)
                self.status_controller.finish(status)
                return count

            self.log.debug(
                f"Preparing {num_comics} comics for creation in library {self.library.path}."
            )
            self.status_controller.start(status)

            self.metadata[FTS_CREATE] = {}
            create_comics = []
            for path in paths:
                if self.abort_event.is_set():
                    return count
                try:
                    self._bulk_create_comic(path, create_comics)
                except KeyError:
                    self.log.warning(f"No comic metadata for {path}")
                    self.log.exception(f"Error preparing {path} for create.")
                except Exception:
                    self.log.exception(f"Error preparing {path} for create.")
            self.metadata.pop(CREATE_COMICS)
            self.metadata.pop(LINK_FKS)

            num_comics = len(create_comics)
            if num_comics:
                self.log.debug(f"Bulk creating {num_comics} comics...")
                created_comics = Comic.objects.bulk_create(
                    create_comics,
                    update_conflicts=True,
                    update_fields=BULK_CREATE_COMIC_FIELDS,
                    unique_fields=Comic._meta.unique_together[0],
                )
                count = len(created_comics)

                # Replace FTS_CREATE path keyed entries with pk keys
                for created_comic in created_comics:
                    self.metadata[FTS_CREATE][created_comic.pk] = self.metadata[
                        FTS_CREATE
                    ].pop(created_comic.path)
        except Exception:
            self.log.exception(f"While creating {num_comics} comics")
        finally:
            self.status_controller.finish(status)
        return count
