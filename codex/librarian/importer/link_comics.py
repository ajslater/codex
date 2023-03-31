"""Bulk update m2m fields."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import (
    Comic,
    Creator,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.threads import QueuedThread


class LinkComicsMixin(QueuedThread):
    """Link comics methods."""

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
    def _link_creators(creators_md):
        """Get the ids of all creators to link."""
        if not creators_md:
            return set()
        creators_filter = Q()
        for creator in creators_md:
            filter_dict = {
                "role__name": creator.get("role"),
                "person__name": creator["person"],
            }
            creators_filter |= Q(**filter_dict)
        creator_pks = Creator.objects.filter(creators_filter).values_list(
            "pk", flat=True
        )
        return frozenset(creator_pks)

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
            if "creators" not in all_m2m_links:
                all_m2m_links["creators"] = {}
            creators_md = md.pop("creators", None)
            all_m2m_links["creators"][comic_pk] = self._link_creators(creators_md)
            self._link_named_m2ms(all_m2m_links, comic_pk, md)
        return all_m2m_links

    def _query_relation_adjustments(
        self, m2m_links, ThroughModel, through_field_id_name, status  # noqa: N803
    ):
        all_del_pks = set()
        tms = []
        for comic_pk, pks in m2m_links.items():
            del_query = ~Q(**{through_field_id_name + "__in": pks})
            del_pks = (
                ThroughModel.objects.filter(comic_id=comic_pk)
                .filter(del_query)
                .values_list("pk", flat=True)
            )
            all_del_pks |= set(del_pks)
            if status:
                status.total += len(del_pks)
                self.status_controller.update(status)

            extant_pks = set(
                ThroughModel.objects.filter(comic_id=comic_pk).values_list(
                    through_field_id_name, flat=True
                )
            )
            missing_pks = set(pks) - extant_pks
            if status:
                status.total += len(missing_pks)
                self.status_controller.update(status)
            for pk in missing_pks:
                defaults = {"comic_id": comic_pk, through_field_id_name: pk}
                tm = ThroughModel(**defaults)
                tms.append(tm)
        return tms, all_del_pks

    def bulk_fix_comic_m2m_field(self, field_name, m2m_links, status):
        """Recreate an m2m field for a set of comics.

        Since we can't bulk_update or bulk_create m2m fields use a trick.
        bulk_create() on the through table:
        https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452
        https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ManyToManyField.through
        """
        field = getattr(Comic, field_name)
        ThroughModel = field.through  # noqa: N806

        model = Comic._meta.get_field(field_name).related_model
        if model is None:
            reason = f"Bad model from {field_name}"
            raise ValueError(reason)
        link_name = model.__name__.lower()
        through_field_id_name = f"{link_name}_id"

        tms, all_del_pks = self._query_relation_adjustments(
            m2m_links, ThroughModel, through_field_id_name, status
        )
        if status:
            status.total += len(tms) + len(all_del_pks)
            self.status_controller.update(status)

        update_fields = ("comic_id", through_field_id_name)
        ThroughModel.objects.bulk_create(
            tms,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=update_fields,
        )
        if created_count := len(tms):
            self.log.info(
                f"Created {created_count} new {field_name}"
                " relations for altered comics."
            )
        if status:
            status.complete += created_count
            self.status_controller.update(status)

        if del_count := len(all_del_pks):
            ThroughModel.objects.filter(comic_id__in=all_del_pks).delete()
            self.log.info(
                f"Deleted {del_count} stale {field_name} relations for altered comics.",
            )
        if status:
            status.complete += del_count
            self.status_controller.update(status)

    @status_notify(status_type=ImportStatusTypes.LINK_M2M_FIELDS, updates=False)
    def bulk_query_and_link_comic_m2m_fields(self, all_m2m_mds, status=None):
        """Combine query and bulk link into a batch."""
        if status:
            status.complete = 0
            status.total = 0
        all_m2m_links = self._link_comic_m2m_fields(all_m2m_mds)
        for field_name, m2m_links in all_m2m_links.items():
            try:
                self.bulk_fix_comic_m2m_field(field_name, m2m_links, status)
            except Exception:
                self.log.exception(f"Error recreating m2m field: {field_name}")

        count = len(all_m2m_links)
        self.log.info(f"Linked {count} comics to tags.")
        return count
