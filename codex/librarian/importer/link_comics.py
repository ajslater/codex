"""Bulk update m2m fields."""
from logging import DEBUG, INFO
from pathlib import Path

from django.db.models import Q

from codex.models import (
    Comic,
    Credit,
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

    def _query_relation_adjustments(
        self, field_name, m2m_links, ThroughModel  # noqa: N803
    ):
        self.log.debug(
            f"Determining {field_name} relation adjustments for altered comics."
        )
        model = Comic._meta.get_field(field_name).related_model
        if model is None:
            raise ValueError(f"Bad model from {field_name}")
        link_name = model.__name__.lower()
        through_field_id_name = f"{link_name}_id"

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
            extant_pks = set(
                ThroughModel.objects.filter(comic_id=comic_pk).values_list(
                    through_field_id_name, flat=True
                )
            )
            missing_pks = set(pks) - extant_pks
            for pk in missing_pks:
                defaults = {"comic_id": comic_pk, through_field_id_name: pk}
                tm = ThroughModel(**defaults)
                tms.append(tm)
        return tms, all_del_pks

    def bulk_fix_comic_m2m_field(self, field_name, m2m_links):
        """Recreate an m2m field for a set of comics.

        Since we can't bulk_update or bulk_create m2m fields use a trick.
        bulk_create() on the through table:
        https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452
        https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ManyToManyField.through
        """
        field = getattr(Comic, field_name)
        ThroughModel = field.through  # noqa: N806

        tms, all_del_pks = self._query_relation_adjustments(
            field_name, m2m_links, ThroughModel
        )

        created_objs = ThroughModel.objects.bulk_create(tms)
        created_count = len(created_objs)
        if created_count:
            level = INFO
        else:
            level = DEBUG
        self.log.log(
            level,
            f"Created {created_count} new {field_name} relations for altered comics.",
        )

        (del_count, _) = ThroughModel.objects.filter(comic_id__in=all_del_pks).delete()
        if del_count:
            level = INFO
        else:
            level = DEBUG
        self.log.log(
            level,
            f"Deleted {del_count} stale {field_name} relations for altered comics.",
        )
        return created_count + del_count

    def bulk_link_comic_m2m_fields(self, all_m2m_links):
        """Create and recreate links to m2m fields in bulk."""
        for field_name, m2m_links in all_m2m_links.items():
            try:
                self.bulk_fix_comic_m2m_field(field_name, m2m_links)
            except Exception as exc:
                self.log.error(f"Error recreating m2m field: {field_name}")
                self.log.exception(exc)

    def bulk_query_and_link_comic_m2m_fields(
        self, _library, all_m2m_mds, count, _total
    ):
        """Combine query and bulk link into a batch."""
        count = len(all_m2m_mds)
        all_m2m_links = self._link_comic_m2m_fields(all_m2m_mds)
        self.bulk_link_comic_m2m_fields(all_m2m_links)
        return count
