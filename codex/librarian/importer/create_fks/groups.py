"""Create missing browser group foreign keys."""

from django.core.exceptions import ObjectDoesNotExist

from codex.librarian.importer.const import (
    CLASS_CUSTOM_COVER_GROUP_MAP,
    COUNT_FIELDS,
    GROUP_UPDATE_FIELDS,
    IMPRINT,
    ISSUE_COUNT,
    PUBLISHER,
    SERIES,
    VOLUME_COUNT,
)
from codex.librarian.importer.create_covers import CreateCoversImporter
from codex.models import (
    CustomCover,
    Imprint,
    Publisher,
    Series,
    Volume,
)


class CreateForeignKeysBrowserGroupsImporter(CreateCoversImporter):
    """Methods for creating browser group foreign keys."""

    @staticmethod
    def _add_custom_cover_to_group(group_class, obj):
        """If a custom cover exists for this group, add it."""
        group = CLASS_CUSTOM_COVER_GROUP_MAP.get(group_class)
        if not group:
            # Normal, volume doesn't link to covers
            return
        try:
            cover = CustomCover.objects.filter(group=group, sort_name=obj.sort_name)[0]
            obj.custom_cover = cover
        except (IndexError, ObjectDoesNotExist):
            pass

    @classmethod
    def _create_group_obj(cls, group_class, group_param_tuple, group_count):
        """Create a set of browser group objects."""
        defaults = {"name": group_param_tuple[-1]}
        if group_class in (Imprint, Series, Volume):
            defaults[PUBLISHER] = Publisher.objects.get(name=group_param_tuple[0])
        if group_class in (Series, Volume):
            defaults[IMPRINT] = Imprint.objects.get(
                publisher=defaults[PUBLISHER],
                name=group_param_tuple[1],
            )

        if group_class is Series:
            defaults[VOLUME_COUNT] = group_count
        elif group_class is Volume:
            defaults[SERIES] = Series.objects.get(
                publisher=defaults[PUBLISHER],
                imprint=defaults[IMPRINT],
                name=group_param_tuple[2],
            )
            defaults[ISSUE_COUNT] = group_count

        obj = group_class(**defaults)
        obj.presave()
        cls._add_custom_cover_to_group(group_class, obj)
        return obj

    @staticmethod
    def _update_group_obj(group_class, group_param_tuple, group_count):
        """Update group counts for a Series or Volume."""
        if group_count is None:
            return None
        search_kwargs = {
            f"{PUBLISHER}__name": group_param_tuple[0],
            f"{IMPRINT}__name": group_param_tuple[1],
            "name": group_param_tuple[-1],
        }
        if group_class == Volume:
            search_kwargs[f"{SERIES}__name"] = group_param_tuple[2]

        obj = group_class.objects.get(**search_kwargs)
        count_field = COUNT_FIELDS[group_class]
        if count_field is not None:
            obj_count = getattr(obj, count_field)
            if obj_count is None or group_count > obj_count:
                setattr(obj, count_field, group_count)
            else:
                obj = None
        return obj

    def bulk_group_create(self, group_tree_counts, group_class, status):
        """Bulk creates groups."""
        count = 0
        if not group_tree_counts:
            return
        create_groups = []
        for group_param_tuple, group_count in group_tree_counts.items():
            obj = self._create_group_obj(group_class, group_param_tuple, group_count)
            create_groups.append(obj)
        update_fields = GROUP_UPDATE_FIELDS[group_class]
        if group_class in CLASS_CUSTOM_COVER_GROUP_MAP:
            update_fields += ("custom_cover",)
        group_class.objects.bulk_create(
            create_groups,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=group_class._meta.unique_together[0],
        )
        count += len(create_groups)
        if count:
            vnp = group_class._meta.verbose_name_plural.title()
            self.log.info(f"Created {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)
        return

    def bulk_group_updater(self, group_tree_counts, group_class, status):
        """Bulk update groups."""
        if not group_tree_counts:
            return
        update_groups = []
        for group_param_tuple, group_count in group_tree_counts.items():
            obj = self._update_group_obj(group_class, group_param_tuple, group_count)
            if obj:
                update_groups.append(obj)
        count_field = COUNT_FIELDS[group_class]
        group_class.objects.bulk_update(update_groups, fields=[count_field])
        count = len(update_groups)
        if count:
            vnp = group_class._meta.verbose_name_plural.title()
            self.log.info(f"Updated {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)
