"""Bulk update and create comic objects and bulk update m2m fields."""
from pathlib import Path
from time import time

from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Comic,
    Credit,
    Folder,
    Imprint,
    Publisher,
    Series,
    Timestamp,
    Volume,
)
from codex.threads import QueuedThread

_EXCLUDE_BULK_UPDATE_COMIC_FIELDS = {
    "created_at",
    "searchresult",
    "id",
    "bookmark",
}
_BULK_UPDATE_COMIC_FIELDS = []
for field in Comic._meta.get_fields():
    if (not field.many_to_many) and (
        field.name not in _EXCLUDE_BULK_UPDATE_COMIC_FIELDS
    ):
        _BULK_UPDATE_COMIC_FIELDS.append(field.name)


class CreateComicsMixin(QueuedThread):
    """Create comics methods."""

    @staticmethod
    def _get_group_name(group_class, md):
        """Get the name of the browse group."""
        field_name = group_class.__name__.lower()
        return md.get(field_name, group_class.DEFAULT_NAME)

    @classmethod
    def _link_comic_fks(cls, md, library, path):
        """Link all foreign keys."""
        publisher_name = cls._get_group_name(Publisher, md)
        imprint_name = cls._get_group_name(Imprint, md)
        series_name = cls._get_group_name(Series, md)
        volume_name = cls._get_group_name(Volume, md)
        md["library"] = library
        md["publisher"] = Publisher.objects.get(name=publisher_name)
        md["imprint"] = Imprint.objects.get(
            publisher__name=publisher_name, name=imprint_name
        )
        md["series"] = Series.objects.get(
            publisher__name=publisher_name, imprint__name=imprint_name, name=series_name
        )
        md["volume"] = Volume.objects.get(
            publisher__name=publisher_name,
            imprint__name=imprint_name,
            series__name=series_name,
            name=volume_name,
        )
        parent_path = Path(path).parent
        md["parent_folder"] = Folder.objects.get(path=parent_path)

    def _update_comics(self, library, comic_paths: set, mds) -> tuple[int, frozenset]:
        """Bulk update comics."""
        if not comic_paths:
            return 0, frozenset()

        self.log.debug(
            f"Preparing {len(comic_paths)} comics for update in library {library.path}."
        )
        # Get existing comics to update
        comics = Comic.objects.filter(library=library, path__in=comic_paths).only(
            *_BULK_UPDATE_COMIC_FIELDS
        )

        # set attributes for each comic
        update_comics = []
        now = Now()
        comic_pks = []
        comic_update_paths = set()
        for comic in comics:
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
            count = Comic.objects.bulk_update(update_comics, _BULK_UPDATE_COMIC_FIELDS)
            if not count:
                count = 0

            task = CoverRemoveTask(frozenset(comic_pks))
            self.log.debug(f"Purging covers for {len(comic_pks)} updated comics.")
            self.librarian_queue.put(task)
        except Exception as exc:
            count = 0
            self.log.error(exc)
            self.log.error("While updating", comic_update_paths)

        return (count, converted_create_paths)

    def _create_comics(self, library, comic_paths, mds):
        """Bulk create comics."""
        if not comic_paths:
            return 0

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
            created_comics = Comic.objects.bulk_create(create_comics)
            created_count = len(created_comics)
        except Exception as exc:
            created_count = 0
            self.log.error(exc)
            self.log.error("While creating", comic_paths)

        return created_count

    @staticmethod
    def _link_folders(folder_paths):
        """Get the ids of all folders to link."""
        if not folder_paths:
            return set()
        folder_pks = Folder.objects.filter(path__in=folder_paths).values_list(
            "pk", flat=True
        )
        return frozenset(folder_pks)

    @staticmethod
    def _link_credits(credits):
        """Get the ids of all credits to link."""
        if not credits:
            return set()
        filter = Q()
        for credit in credits:
            filter_dict = {
                "role__name": credit.get("role"),
                "person__name": credit["person"],
            }
            filter = filter | Q(**filter_dict)
        credit_pks = Credit.objects.filter(filter).values_list("pk", flat=True)
        return frozenset(credit_pks)

    def _link_named_m2ms(self, all_m2m_links, comic_pk, md):
        """Set the ids of all named m2m fields into the comic dict."""
        for field, names in md.items():
            related_model = Comic._meta.get_field(field).related_model
            if related_model is None:
                self.log.error(f"No related class found for Comic.{field}")
                continue
            pks = related_model.objects.filter(name__in=names).values_list(
                "pk", flat=True
            )
            if field not in all_m2m_links:
                all_m2m_links[field] = {}
            all_m2m_links[field][comic_pk] = frozenset(pks)

    def _link_comic_m2m_fields(self, m2m_mds):
        """Get the complete m2m field data to create."""
        all_m2m_links = {}
        comic_paths = frozenset(m2m_mds.keys())
        self.log.debug(
            f"Preparing {len(comic_paths)} comics for many to many relation recreation."
        )

        comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
        for comic_pk, comic_path in comics:
            md = m2m_mds[comic_path]
            if "folders" not in all_m2m_links:
                all_m2m_links["folders"] = {}
            try:
                folder_paths = md.pop("folders")
            except KeyError:
                folder_paths = []
            all_m2m_links["folders"][comic_pk] = self._link_folders(folder_paths)
            if "credits" not in all_m2m_links:
                all_m2m_links["credits"] = {}
            try:
                credits = md.pop("credits")
            except KeyError:
                credits = None
            all_m2m_links["credits"][comic_pk] = self._link_credits(credits)
            self._link_named_m2ms(all_m2m_links, comic_pk, md)
        return all_m2m_links

    def bulk_recreate_m2m_field(self, field_name, m2m_links):
        """Recreate an m2m field for a set of comics.

        Since we can't bulk_update or bulk_create m2m fields use a trick.
        bulk_create() on the through table:
        https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452
        https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ManyToManyField.through
        """
        self.log.debug(f"Recreating {field_name} relations for altered comics.")
        field = getattr(Comic, field_name)
        ThroughModel = field.through  # noqa: N806
        model = Comic._meta.get_field(field_name).related_model
        if model is None:
            raise ValueError(f"Bad model from {field_name}")
        link_name = model.__name__.lower()
        through_field_id_name = f"{link_name}_id"
        tms = []
        for comic_pk, pks in m2m_links.items():
            for pk in pks:
                defaults = {"comic_id": comic_pk, through_field_id_name: pk}
                tm = ThroughModel(**defaults)
                tms.append(tm)

        # It is simpler to just nuke and recreate all links than
        #   detect, create & delete them.
        ThroughModel.objects.filter(comic_id__in=m2m_links.keys()).delete()
        ThroughModel.objects.bulk_create(tms)
        self.log.info(
            f"Recreated {len(tms)} {field_name} relations for altered comics."
        )

    def bulk_import_comics(
        self, library, create_paths, update_paths, all_bulk_mds, all_m2m_mds
    ):
        """Bulk import comics."""
        if not (create_paths or update_paths or all_bulk_mds or all_m2m_mds):
            self.status_controller.finish_many(
                (
                    ImportStatusTypes.FILES_MODIFIED,
                    ImportStatusTypes.FILES_CREATED,
                    ImportStatusTypes.LINK_M2M_FIELDS,
                )
            )
            return 0

        update_count = create_count = 0
        try:
            try:
                try:
                    self.status_controller.start(
                        ImportStatusTypes.FILES_MODIFIED, name=f"({len(update_paths)})"
                    )
                    update_count, converted_create_paths = self._update_comics(
                        library, update_paths, all_bulk_mds
                    )
                    create_paths.update(converted_create_paths)
                finally:
                    self.status_controller.finish(ImportStatusTypes.FILES_MODIFIED)
                self.status_controller.start(
                    ImportStatusTypes.FILES_CREATED, name=f"({len(create_paths)})"
                )
                create_count = self._create_comics(library, create_paths, all_bulk_mds)
            finally:
                self.status_controller.finish(ImportStatusTypes.FILES_CREATED)
                # Just to be sure.
            all_m2m_links = self._link_comic_m2m_fields(all_m2m_mds)
            total_links = 0
            for m2m_links in all_m2m_links.values():
                total_links += len(m2m_links)
            self.status_controller.start(ImportStatusTypes.LINK_M2M_FIELDS, total_links)

            since = time()
            completed_links = 0
            for m2m_links in all_m2m_links.values():
                for field_name, m2m_links in all_m2m_links.items():
                    try:
                        self.bulk_recreate_m2m_field(field_name, m2m_links)
                    except Exception as exc:
                        self.log.error(f"Error recreating m2m field: {field_name}")
                        self.log.exception(exc)
                    completed_links = len(m2m_links)
                    since = self.status_controller.update(
                        ImportStatusTypes.LINK_M2M_FIELDS,
                        completed_links,
                        total_links,
                        since=since,
                    )
        finally:
            self.status_controller.finish(ImportStatusTypes.LINK_M2M_FIELDS)

        if update_count:
            Timestamp.touch(Timestamp.COVERS)
        update_log = f"Updated {update_count} Comics."
        self.log.info(update_log)
        create_log = f"Created {create_count} Comics."
        self.log.info(create_log)

        total_count = update_count + create_count
        return total_count
