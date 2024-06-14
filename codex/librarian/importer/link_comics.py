"""Bulk update m2m fields."""

from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.const import (
    COMIC_FK_FIELD_NAMES,
    DICT_MODEL_FIELD_NAME_CLASS_MAP,
    DICT_MODEL_REL_LINK_MAP,
    FOLDERS_FIELD,
    IMPRINT,
    M2M_MDS,
    PARENT_FOLDER,
    PUBLISHER,
    SERIES,
    STORY_ARC_NUMBERS_FK_NAME,
    STORY_ARCS_METADATA_KEY,
    VOLUME,
)
from codex.librarian.importer.link_covers import LinkCoversImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.models.named import Identifier
from codex.status import Status


class LinkComicsImporter(LinkCoversImporter):
    """Link comics methods."""

    @staticmethod
    def _get_group_name(group_class, md):
        """Get the name of the browse group."""
        field_name = group_class.__name__.lower()
        return md.get(field_name, group_class.DEFAULT_NAME)

    @classmethod
    def get_comic_fk_links(cls, md, path):
        """Get links for all foreign keys for creating and updating."""
        publisher_name = cls._get_group_name(Publisher, md)
        imprint_name = cls._get_group_name(Imprint, md)
        series_name = cls._get_group_name(Series, md)
        volume_name = cls._get_group_name(Volume, md)
        md[PUBLISHER] = Publisher.objects.get(name=publisher_name)
        md[IMPRINT] = Imprint.objects.get(
            publisher__name=publisher_name, name=imprint_name
        )
        md[SERIES] = Series.objects.get(
            publisher__name=publisher_name, imprint__name=imprint_name, name=series_name
        )
        md[VOLUME] = Volume.objects.get(
            publisher__name=publisher_name,
            imprint__name=imprint_name,
            series__name=series_name,
            name=volume_name,
        )
        parent_path = Path(path).parent
        md[PARENT_FOLDER] = Folder.objects.get(path=parent_path)
        for field_name in COMIC_FK_FIELD_NAMES:
            name = md.pop(field_name, None)
            if name and (fk_class := Comic._meta.get_field(field_name).related_model):
                md[field_name] = fk_class.objects.get(name=name)

    @staticmethod
    def _get_link_folders_filter(_field_name, folder_paths):
        """Get the ids of all folders to link."""
        return Q(path__in=folder_paths)

    @staticmethod
    def _get_link_identifier_filter(field_name, dict_md):
        """Get the ids of all dict style objects to link."""
        dict_filter = Q()
        key_rel, value_rel = DICT_MODEL_REL_LINK_MAP[field_name]
        for key, values_dict in dict_md.items():
            nss = values_dict.get("nss")
            dict_filter |= Q(**{key_rel: key, value_rel: nss})
        return dict_filter

    @staticmethod
    def _get_link_dict_filter(field_name, dict_md):
        """Get the ids of all dict style objects to link."""
        dict_filter = Q()
        key_rel, value_rel = DICT_MODEL_REL_LINK_MAP[field_name]
        for key, value in dict_md.items():
            rel_dict = {key_rel: key, value_rel: value}
            dict_filter |= Q(**rel_dict)
        return dict_filter

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

    def _link_prepare_special_m2ms(self, link_data, key, model, get_link_filter_method):
        """Prepare special m2m for linking."""
        (all_m2m_links, md, comic_pk) = link_data
        values = md.pop(key, [])
        if not values:
            return
        if key == STORY_ARCS_METADATA_KEY:
            key = STORY_ARC_NUMBERS_FK_NAME
        if key not in all_m2m_links:
            all_m2m_links[key] = {}

        m2m_filter = get_link_filter_method(key, values)
        pks = model.objects.filter(m2m_filter).values_list("pk", flat=True).distinct()
        result = frozenset(pks)
        all_m2m_links[key][comic_pk] = result

    def _link_comic_m2m_fields(self):
        """Get the complete m2m field data to create."""
        all_m2m_links = {}
        comic_paths = frozenset(self.metadata.get(M2M_MDS, {}).keys())
        if not comic_paths:
            return all_m2m_links
        comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
        for comic_pk, comic_path in comics:
            md = self.metadata[M2M_MDS][comic_path]
            link_data = (all_m2m_links, md, comic_pk)
            self._link_prepare_special_m2ms(
                link_data, FOLDERS_FIELD, Folder, self._get_link_folders_filter
            )
            for field_name, model in DICT_MODEL_FIELD_NAME_CLASS_MAP:
                if model == Identifier:
                    method = self._get_link_identifier_filter
                else:
                    method = self._get_link_dict_filter
                self._link_prepare_special_m2ms(link_data, field_name, model, method)

            self._link_named_m2ms(all_m2m_links, comic_pk, md)
        self.metadata.pop(M2M_MDS)
        return all_m2m_links

    def _query_relation_adjustments(
        self,
        m2m_links,
        ThroughModel,  # noqa:N803
        through_field_id_name,
        status,
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
                status.total = status.total or 0
                status.total += len(del_pks)
                self.status_controller.update(status)

            extant_pks = set(
                ThroughModel.objects.filter(comic_id=comic_pk).values_list(
                    through_field_id_name, flat=True
                )
            )
            missing_pks = set(pks) - extant_pks
            if status:
                status.total = status.total or 0
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
        status.total = status.total or 0
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
            self.log.info(f"Linked {created_count} new {field_name} to altered comics.")
        status.complete = status.complete or 0
        status.complete += created_count
        self.status_controller.update(status)

        if del_count := len(all_del_pks):
            del_qs = ThroughModel.objects.filter(pk__in=all_del_pks)
            del_qs.delete()
            self.log.info(
                f"Deleted {del_count} stale {field_name} relations for altered comics.",
            )
        status.complete = status.complete or 0
        status.complete += del_count
        self.status_controller.update(status)
        return created_count, del_count

    def bulk_query_and_link_comic_m2m_fields(self):
        """Combine query and bulk link into a batch."""
        status = Status(ImportStatusTypes.LINK_M2M_FIELDS)
        self.status_controller.start(status)
        all_m2m_links = self._link_comic_m2m_fields()
        created_total = 0
        del_total = 0
        for field_name, m2m_links in all_m2m_links.items():
            try:
                created_count, del_count = self.bulk_fix_comic_m2m_field(
                    field_name, m2m_links, status
                )
                created_total += created_count
                del_total += del_count
            except Exception:
                self.log.exception(f"Error recreating m2m field: {field_name}")

        if created_total:
            self.log.info(f"Linked {created_total} comics to tags.")
        if del_total:
            self.log.info(f"Deleted {del_total} stale relations for altered comics.")
        self.status_controller.finish(status)
        return created_total + del_total
