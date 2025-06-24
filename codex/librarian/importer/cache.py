"""Update Groups timestamp for cover cache busting."""

from collections.abc import Mapping
from datetime import datetime
from multiprocessing import Queue

from django.db.models import QuerySet
from django.db.models.aggregates import Count
from django.db.models.functions.datetime import Now
from django.db.models.query import Q

from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status
from codex.librarian.worker import WorkerStatusMixin
from codex.models import StoryArc, Volume
from codex.models.groups import BrowserGroupModel
from codex.models.library import Library
from codex.views.const import GROUP_MODELS

_UPDATE_FIELDS = ("updated_at",)


class TimestampUpdater(WorkerStatusMixin):
    """Update Groups timestamp for cover cache busting."""

    @staticmethod
    def _get_update_filter(
        model: type[BrowserGroupModel],
        start_time: datetime,
        force_update_group_map: Mapping,
        library: Library,
    ):
        # Get groups with comics updated during this import
        rel = "storyarcnumber__" if model == StoryArc else ""
        updated_at_rel = rel + "comic__updated_at__gt"
        library_rel = rel + "comic__library"
        updated_filter = {library_rel: library, updated_at_rel: start_time}
        update_filter = Q(**updated_filter)

        # Get groups with custom covers updated during this import
        if model != Volume:
            update_filter |= Q(custom_cover__updated_at__gt=start_time)

        # Get groups to be force updated (usually those with deleted children)
        if pks := force_update_group_map.get(model):
            update_filter |= Q(pk__in=pks)

        return update_filter

    @staticmethod
    def _add_child_count_filter(qs: QuerySet, model: type[BrowserGroupModel]):
        """Filter out groups with no comics."""
        rel_prefix = "storyarcnumber__" if model == StoryArc else ""
        rel_prefix += "comic"
        qs = qs.alias(child_count=Count(f"{rel_prefix}__pk", distinct=True))
        return qs.filter(child_count__gt=0)

    @classmethod
    def _update_group_model(
        cls,
        force_update_group_map: Mapping,
        model: type[BrowserGroupModel],
        start_time: datetime,
        library: Library,
        log_list,
    ):
        """Update a single group model."""
        update_filter = cls._get_update_filter(
            model, start_time, force_update_group_map, library
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

    def update_all_groups(
        self, force_update_group_map: Mapping, start_time: datetime, library: Library
    ):
        """Update timestamps for each group for cover cache busting."""
        total_count = 0
        status = Status(ImportStatusTypes.UPDATE_GROUP_TIMESTAMPS)
        self.status_controller.start(status)
        try:
            log_list = []
            for model in GROUP_MODELS:
                count = self._update_group_model(
                    force_update_group_map, model, start_time, library, log_list
                )
                if not count:
                    continue
                self.log.debug(f"Updated {count} {model.__name__}s timestamps.")
                status.add_complete(count)
                self.status_controller.update(status)
                total_count += count

            if total_count:
                groups_log = ", ".join(log_list)
                self.log.info(f"Updated timestamps for {groups_log}.")
        finally:
            self.status_controller.finish(status)
        return total_count

    def __init__(self, logger_, librarian_queue: Queue | None):
        """Initialize Worker."""
        self.init_worker(logger_, librarian_queue)
