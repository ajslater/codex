"""Bulk update m2m fields."""

from collections.abc import Mapping

from django.db.models import Q

from codex.librarian.importer.const import (
    FOLDERS_FIELD,
    IDENTIFIER_URL_FIELD_NAME,
    M2M_LINK,
)
from codex.librarian.importer.link.const import (
    DICT_MODEL_FIELD_NAME_CLASS_MAP,
    DICT_MODEL_REL_LINK_MAP,
)
from codex.librarian.importer.link.foreign_keys import LinkComicForiegnKeysImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Comic,
    Folder,
)
from codex.status import Status


class LinkComicsImporter(LinkComicForiegnKeysImporter):
    """Link comics methods."""

    @staticmethod
    def _get_link_folders_filter(_field_name, folder_paths):
        """Get the ids of all folders to link."""
        return Q(path__in=folder_paths)

    @staticmethod
    def _get_link_dict_filter(field_name, values_set):
        """Get the ids of all dict style objects to link."""
        dict_filter = Q()
        rels = DICT_MODEL_REL_LINK_MAP[field_name]
        for values in values_set:
            rel_dict = {
                key: value
                for key, value in zip(rels, values, strict=False)
                if key != IDENTIFIER_URL_FIELD_NAME
            }
            dict_filter |= Q(**rel_dict)
        return dict_filter

    def _link_prepare_special_m2ms(  # noqa: PLR0913
        self, all_m2m_links, md, comic_pk, key, model, link_filter_method
    ):
        """Prepare special m2m for linking."""
        values = md.pop(key, [])
        if not values:
            return
        if key not in all_m2m_links:
            all_m2m_links[key] = {}

        m2m_filter = link_filter_method(key, values)
        pks = model.objects.filter(m2m_filter).values_list("pk", flat=True).distinct()
        result = frozenset(pks)
        all_m2m_links[key][comic_pk] = result

    def _link_named_m2ms(self, all_m2m_links, comic_pk, md):
        """Set the ids of all named m2m fields into the comic dict."""
        total = 0
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
            total += len(pks)
        return total

    def _link_comic_m2m_fields(self) -> tuple[Mapping, int]:
        """Get the complete m2m field data to create."""
        total = 0
        all_m2m_links = {}
        comic_paths = frozenset(self.metadata.get(M2M_LINK, {}).keys())
        if not comic_paths:
            return all_m2m_links, total
        status = Status(ImportStatusTypes.PREPARE_TAG_LINKS, 0, len(comic_paths))
        self.status_controller.start(status)

        comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
        for comic_pk, comic_path in comics:
            md = self.metadata[M2M_LINK][comic_path]
            self._link_prepare_special_m2ms(
                all_m2m_links,
                md,
                comic_pk,
                FOLDERS_FIELD,
                Folder,
                self._get_link_folders_filter,
            )
            for field_name, model in DICT_MODEL_FIELD_NAME_CLASS_MAP:
                self._link_prepare_special_m2ms(
                    all_m2m_links,
                    md,
                    comic_pk,
                    field_name,
                    model,
                    self._get_link_dict_filter,
                )

            total += self._link_named_m2ms(all_m2m_links, comic_pk, md)
            status.increment_complete()
            self.status_controller.update(status)
        self.metadata.pop(M2M_LINK)
        self.status_controller.finish(status)
        return all_m2m_links, total

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
        """
        Recreate an m2m field for a set of comics.

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
        all_m2m_links, link_total = self._link_comic_m2m_fields()
        status = Status(ImportStatusTypes.LINK_COMICS_TO_TAGS, None, None)
        self.status_controller.start(status)
        status.complete = 0
        status.total = link_total
        self.status_controller.update(status)
        created_total = 0
        del_total = 0
        for field_name, m2m_links in all_m2m_links.items():
            try:
                created_count, del_count = self.bulk_fix_comic_m2m_field(
                    field_name, m2m_links, status
                )
                created_total += created_count
                del_total += del_count
                status.complete += created_count + del_count
                self.status_controller.update(status)
            except Exception:
                self.log.exception(f"Error recreating m2m field: {field_name}")

        if created_total:
            self.log.info(f"Linked {created_total} comics to tags.")
        if del_total:
            self.log.info(f"Deleted {del_total} stale relations for altered comics.")
        self.status_controller.finish(status)
        return created_total + del_total
