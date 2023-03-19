"""Bulk update and create comic objects and bulk update m2m fields."""
from codex.librarian.importer.link_comics import LinkComicsMixin
from codex.librarian.importer.update_comics import BULK_UPDATE_COMIC_FIELDS
from codex.models import (
    Comic,
)


class CreateComicsMixin(LinkComicsMixin):
    """Create comics methods."""

    def bulk_create_comics(self, comic_paths, _status_args, library, mds):
        """Bulk create comics."""
        this_count = 0
        if not comic_paths:
            return this_count

        num_comics = len(comic_paths)
        self.log.debug(
            f"Preparing {num_comics} comics for creation in library {library.path}."
        )
        # prepare create comics
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
            except Exception as exc:
                self.log.error(f"Error preparing {path} for create.")
                self.log.exception(exc)

        num_comics = len(create_comics)
        self.log.info(
            f"Prepared {num_comics} comics for creation in library {library.path}."
        )
        self.log.debug(f"Bulk creating {num_comics} comics...")
        try:
            created_comics = Comic.objects.bulk_create(
                create_comics,
                update_conflicts=True,
                update_fields=BULK_UPDATE_COMIC_FIELDS,
                unique_fields=Comic._meta.unique_together[0],
            )
            this_count += len(created_comics)
        except Exception as exc:
            self.log.error(exc)
            self.log.error("While creating", comic_paths)

        return this_count
