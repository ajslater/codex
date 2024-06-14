"""Update Groups timestamp for cover cache busting."""

from django.db.models.aggregates import Count
from django.db.models.functions.datetime import Now
from django.db.models.query import Q

from codex.librarian.importer.init import InitImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import StoryArc, Volume
from codex.status import Status
from codex.views.const import GROUP_MODELS

_UPDATE_FIELDS = ("updated_at",)


class CacheUpdateImporter(InitImporter):
    """Update Groups timestamp for cover cache busting."""

    @staticmethod
    def _get_update_filter(model, start_time, force_update_group_map):
        # Get groups with comics updated during this import
        rel = "storyarcnumber__" if model == StoryArc else ""
        updated_at_rel = rel + "comic__updated_at__gt"
        updated_filter = {updated_at_rel: start_time}
        update_filter = Q(**updated_filter)

        # Get groups with custom covers updated during this import
        if model != Volume:
            update_filter |= Q(custom_cover__updated_at__gt=start_time)

        # Get groups to be force updated (usually those with deleted children)
        if pks := force_update_group_map.get(model):
            update_filter |= Q(pk__in=pks)

        return update_filter

    @staticmethod
    def _add_child_count_filter(qs, model):
        """Filter out groups with no comics."""
        rel_prefix = "storyarcnumber__" if model == StoryArc else ""
        rel_prefix += "comic"
        qs = qs.alias(child_count=Count(f"{rel_prefix}__pk", distinct=True))
        return qs.filter(child_count__gt=0)

    @classmethod
    def _update_group_model(cls, force_update_group_map, model, start_time, log_list):
        """Update a single group model."""
        update_filter = cls._get_update_filter(
            model, start_time, force_update_group_map
        )
        qs = model.objects.filter(update_filter)
        qs = cls._add_child_count_filter(qs, model)

        qs = qs.distinct()
        qs = qs.only(*_UPDATE_FIELDS)

        updated = []
        for obj in qs:
            obj.updated_at = Now()
            updated.append(obj)

        count = len(updated)
        if count:
            model.objects.bulk_update(updated, _UPDATE_FIELDS)
            log_list.append(f"{count} {model.__name__}s")
        return count

    def update_all_groups(self, force_update_group_map, start_time):
        """Update timestamps for each group for cover cache busting."""
        total_count = 0
        status = Status(ImportStatusTypes.GROUP_UPDATE)
        self.status_controller.start(status)
        try:
            log_list = []
            for model in GROUP_MODELS:
                # self.log.debug(f"Updating timestamps for {model.__name__}s...")
                count = self._update_group_model(
                    force_update_group_map, model, start_time, log_list
                )
                if count:
                    self.log.debug(f"Updated {count} {model.__name__}s timestamps.")
                status.add_complete(count)
                self.status_controller.update(status, notify=False)
                total_count += count

            if total_count:
                groups_log = ", ".join(log_list)
                self.log.info(  # type: ignore
                    f"Updated timestamps for {groups_log}."
                )
                self.changed += total_count
        finally:
            self.status_controller.finish(status)
