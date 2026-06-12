"""Bulk update and create comic objects and bulk update m2m fields."""

from typing import TYPE_CHECKING, cast

from django.db.models import NOT_PROVIDED
from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    ALWAYS_UPDATE_COMIC_FIELDS,
    BULK_CREATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS_SET,
    COLLECTION_FIELD_NAMES,
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
from codex.librarian.status import Status
from codex.models import Comic
from codex.settings import IMPORTER_UPDATE_COMIC_BATCH_SIZE

if TYPE_CHECKING:
    from codex.models.collections import BrowserCollectionModel


class CreateComicsImporter(CreateForeignKeyLinksImporter):
    """Create comics methods."""

    def _populate_fts_attribute_values(self, key: str, sub_key: str | int, md) -> None:
        if sub_key not in self.metadata[key]:
            self.metadata[key][sub_key] = {}
        for field_name, value in md.items():
            if field_name not in NON_FTS_FIELDS:
                self.metadata[key][sub_key][field_name] = (value,)

    def _record_moved_source_collections(
        self, comic: Comic, old_collection_pks: dict[str, int | None]
    ) -> None:
        """
        Stash collections this comic just moved OUT of (changed FK).

        ``TimestampUpdater`` only re-stamps a collection a *current* comic
        still points into, so a publisher/imprint/series/volume change would
        leave the *source* collection's ``updated_at`` stale and the browser's
        ``library.changed`` refresh gate blind to the source view's change.
        The delete phase folds these pks into its force-update map.
        """
        for field_name, old_pk in old_collection_pks.items():
            if old_pk is None or old_pk == getattr(comic, f"{field_name}_id"):
                continue
            # COLLECTION_FIELD_NAMES are always concrete collection FKs.
            model = cast(
                "type[BrowserCollectionModel]",
                Comic._meta.get_field(field_name).related_model,
            )
            self.moved_source_collections.setdefault(model, set()).add(old_pk)

    def _update_comic_values(
        self, comic: Comic, update_comics: list, comic_pks: list, changed_fields: set
    ) -> None:
        md = self.metadata[UPDATE_COMICS].pop(comic.pk, {})
        for field_name, value in md.items():
            setattr(comic, field_name, value)
        changed_fields.update(md)

        self._populate_fts_attribute_values(FTS_UPDATE, comic.pk, md)
        # Snapshot the collection FKs before linking overwrites them so a move
        # re-stamps the collection the comic left (see
        # ``_record_moved_source_collections``).
        old_collection_pks = {
            field_name: getattr(comic, f"{field_name}_id")
            for field_name in COLLECTION_FIELD_NAMES
        }
        link_md = self.get_comic_fk_links(comic.pk, comic.path, for_create=False)
        changed_fields.update(link_md)
        for field_name, value in link_md.items():
            set_value = value
            if set_value is None:
                default_value = Comic._meta.get_field(field_name).default
                if default_value != NOT_PROVIDED:
                    set_value = default_value
            setattr(comic, field_name, set_value)
        self._record_moved_source_collections(comic, old_collection_pks)
        comic.presave()
        comic.updated_at = Now()
        update_comics.append(comic)
        comic_pks.append(comic.pk)

    def update_comics(self) -> int:
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
            # FTS_UPDATE accumulates across chunks; setdefault preserves
            # entries already populated by an earlier chunk's pass.
            self.metadata.setdefault(FTS_UPDATE, {})
            # Get existing comics to update
            comics = Comic.objects.filter(library=self.library, pk__in=pks).only(
                PATH_FIELD_NAME, *BULK_UPDATE_COMIC_FIELDS
            )

            # set attributes for each comic
            update_comics = []
            comic_pks = []
            changed_fields: set[str] = set()
            for comic in comics:
                if self.abort_event.is_set():
                    return count
                try:
                    self._update_comic_values(
                        comic, update_comics, comic_pks, changed_fields
                    )
                except Exception:
                    self.log.exception(f"Error preparing {comic} for update.")
            self.metadata.pop(UPDATE_COMICS)

            count = len(update_comics)
            if count:
                # Write only fields some comic actually changed plus the
                # presave-derived/timestamp set — CASE-WHEN bulk_update
                # cost scales with rows x fields.
                update_fields = sorted(
                    ALWAYS_UPDATE_COMIC_FIELDS
                    | (changed_fields & BULK_UPDATE_COMIC_FIELDS_SET)
                )
                self.log.debug(
                    f"Bulk updating {len(update_comics)} comics on {len(update_fields)} fields."
                )
                Comic.objects.bulk_update(
                    update_comics,
                    update_fields,
                    batch_size=IMPORTER_UPDATE_COMIC_BATCH_SIZE,
                )
                if comic_pks:
                    self.log.debug(
                        f"Purging covers for {len(comic_pks)} updated comics."
                    )
                    self.remove_covers(comic_pks, custom=False)
                    # Queue cover regeneration for the just-purged
                    # comics. Stash here; ``create_and_update`` submits
                    # a single coalesced ``CoverCreateTask`` after
                    # ``create_comics`` has added its own pks.
                    self.cover_create_pks.update(comic_pks)
        except Exception:
            self.log.exception(f"While updating comics: {pks}")
        finally:
            self.status_controller.finish(status)
        return count

    def _bulk_create_comic(self, path: str, create_comics: list[Comic]) -> None:
        md = self.metadata[CREATE_COMICS].pop(path, {})
        self._populate_fts_attribute_values(FTS_CREATE, path, md)
        link_md = self.get_comic_fk_links(path, path, for_create=True)
        md.update(link_md)
        if not md:
            return
        comic = Comic(**md, library=self.library)
        comic.presave()
        create_comics.append(comic)

    def _create_comic_bulk_prepare(
        self, num_comics: int, paths: tuple[str, ...], status: Status
    ) -> list[Comic]:

        self.log.debug(
            f"Preparing {num_comics} comics for creation in library {self.library.path}."
        )
        self.status_controller.start(status)

        # FTS_CREATE accumulates across chunks (see FTS_UPDATE above).
        self.metadata.setdefault(FTS_CREATE, {})
        create_comics = []
        for path in paths:
            if self.abort_event.is_set():
                return []
            try:
                self._bulk_create_comic(path, create_comics)
            except KeyError:
                self.log.warning(f"No comic tags for {path}")
                self.log.exception(f"Error preparing {path} for create.")
            except Exception:
                self.log.exception(f"Error preparing {path} for create.")
        self.metadata.pop(CREATE_COMICS)
        self.metadata.pop(LINK_FKS)
        return create_comics

    def _create_comics_bulk_create(
        self, num_comics: int, create_comics: list[Comic]
    ) -> int:
        self.log.debug(f"Bulk creating {num_comics} comics...")
        created_comics = Comic.objects.bulk_create(
            create_comics,
            update_conflicts=True,
            update_fields=BULK_CREATE_COMIC_FIELDS,
            unique_fields=Comic._meta.unique_together[0],
        )
        count = len(created_comics)

        # Replace FTS_CREATE path keyed entries with pk keys
        created_pks = []
        for created_comic in created_comics:
            self.metadata[FTS_CREATE][created_comic.pk] = self.metadata[FTS_CREATE].pop(
                created_comic.path
            )
            created_pks.append(created_comic.pk)
        created_pks = tuple(created_pks)

        # Stash newly-created comic pks for pre-warming. The actual
        # ``CoverCreateTask`` is submitted by ``create_and_update``
        # after ``update_comics`` has stashed its pks too — coalescing
        # the two phases into a single cover-thread task so the
        # ``CreateCoversStatus`` row doesn't blink between them.
        if created_pks:
            self.cover_create_pks.update(created_pks)
        return count

    def create_comics(self) -> int:
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

            create_comics = self._create_comic_bulk_prepare(num_comics, paths, status)
            num_comics = len(create_comics)
            if num_comics:
                count = self._create_comics_bulk_create(num_comics, create_comics)
        except Exception:
            self.log.exception(f"While creating {num_comics} comics")
        finally:
            self.status_controller.finish(status)
        return count
