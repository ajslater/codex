"""Bulk update and create comic objects and bulk update m2m fields."""
from codex.librarian.importer.link_comics import LinkComicsMixin
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.librarian.importer.update_comics import BULK_UPDATE_COMIC_FIELDS
from codex.models import (
    Comic,
)


class CreateComicsMixin(LinkComicsMixin):
    """Create comics methods."""

    @status_notify(status_type=ImportStatusTypes.FILES_CREATED, updates=False)
    def bulk_create_comics(self, comic_paths, library, mds, **kwargs):
        """Bulk create comics."""
        if not comic_paths:
            return 0
        num_comics = len(comic_paths)

        # prepare create comics
        self.log.debug(
            f"Preparing {num_comics} comics for creation in library {library.path}."
        )
        create_comics = []
        for path in comic_paths:
            try:
                md = mds.pop(path)
                self._link_comic_fks(md, library, path)
                comic = Comic(**md)
                comic.presave()
                comic.set_stat()
                create_comics.append(comic)
            except KeyError:
                self.log.warning(f"No comic metadata for {path}")
            except Exception:
                self.log.exception(f"Error preparing {path} for create.")

        self.log.debug(f"Bulk creating {num_comics} comics...")
        count = 0
        try:
            Comic.objects.bulk_create(
                create_comics,
                update_conflicts=True,
                update_fields=BULK_UPDATE_COMIC_FIELDS,
                unique_fields=Comic._meta.unique_together[0],  # type: ignore
            )
            count = len(create_comics)
            self.log.info(f"Created {count} comics.")
        except Exception:
            self.log.exception(f"While creating {comic_paths}")

        return count
