"""Move comics that need only updating into correct structure."""

from codex.librarian.scribe.importer.const import (
    BULK_UPDATE_COMIC_FIELDS,
    CREATE_COMICS,
    UPDATE_COMICS,
)
from codex.librarian.scribe.importer.query.query_fks import (
    QueryForeignKeysQueryImporter,
)
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateComicsStatus,
    ImporterUpdateComicsStatus,
)
from codex.librarian.scribe.importer.statii.query import ImporterQueryComicUpdatesStatus
from codex.models import Comic


class QueryUpdateComics(QueryForeignKeysQueryImporter):
    """Move comics that need only updating into correct structure."""

    def query_update_comics(self):
        """Pop existing comics from create & move to update if needed."""
        paths = tuple(self.metadata[CREATE_COMICS].keys())
        status = ImporterQueryComicUpdatesStatus(0, len(paths))
        try:
            if not paths:
                return
            self.status_controller.start(status)

            comics = Comic.objects.filter(library=self.library, path__in=paths).only(
                *BULK_UPDATE_COMIC_FIELDS
            )
            status.increment_complete(len(paths) - comics.count())

            for comic in comics:
                if self.abort_event.is_set():
                    return
                proposed_comic_dict = self.metadata[CREATE_COMICS].pop(comic.path)
                update_comic_dict = {
                    key: value
                    for key, value in proposed_comic_dict.items()
                    if getattr(comic, key) != value
                }
                if update_comic_dict:
                    self.metadata[UPDATE_COMICS][comic.pk] = update_comic_dict
                status.increment_complete()
                self.status_controller.update(status)

            create_status = ImporterCreateComicsStatus(
                None, len(self.metadata[CREATE_COMICS])
            )
            self.status_controller.update(create_status)
            update_status = ImporterUpdateComicsStatus(
                None, len(self.metadata[UPDATE_COMICS])
            )
            self.status_controller.update(update_status)
        finally:
            self.status_controller.finish(status)
