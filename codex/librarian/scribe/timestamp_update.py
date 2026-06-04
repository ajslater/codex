"""Update Collections timestamp for cover cache busting."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from django.db.models import QuerySet
from django.db.models.aggregates import Count
from django.db.models.functions.datetime import Now
from django.db.models.query_utils import Q
from django.utils import timezone

from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.status import UpdateCollectionTimestampsStatus
from codex.librarian.worker import WorkerStatusBase
from codex.models import StoryArc, Volume
from codex.models.collections import BrowserCollectionModel
from codex.models.library import Library
from codex.views.const import COLLECTION_MODELS

_UPDATE_FIELDS = ("updated_at",)


class TimestampUpdater(WorkerStatusBase):
    """Update Collections timestamp for cover cache busting."""

    @staticmethod
    def _get_update_filter(
        model: type[BrowserCollectionModel],
        start_time: datetime,
        force_update_collection_map: Mapping,
        library: Library,
    ) -> Q:
        # Get collections with comics updated during this import
        rel = "storyarcnumber__" if model == StoryArc else ""
        updated_at_rel = rel + "comic__updated_at__gt"
        library_rel = rel + "comic__library"
        updated_filter = {library_rel: library, updated_at_rel: start_time}
        update_filter = Q(**updated_filter)

        # Get collections with custom covers updated during this import
        if model != Volume:
            update_filter |= Q(custom_cover__updated_at__gt=start_time)

        # Get collections to be force updated (usually those with deleted children)
        if pks := force_update_collection_map.get(model):
            update_filter |= Q(pk__in=pks)

        return update_filter

    @staticmethod
    def _add_child_count_filter(qs: QuerySet, model: type[BrowserCollectionModel]):
        """Filter out collections with no comics."""
        rel_prefix = "storyarcnumber__" if model == StoryArc else ""
        rel_prefix += "comic"
        qs = qs.alias(child_count=Count(f"{rel_prefix}__pk", distinct=True))
        return qs.filter(child_count__gt=0)

    @classmethod
    def _update_collection_model(
        cls,
        force_update_collection_map: Mapping,
        model: type[BrowserCollectionModel],
        start_time: datetime,
        library: Library,
        log_list,
    ) -> int:
        """Update a single collection model."""
        update_filter = cls._get_update_filter(
            model, start_time, force_update_collection_map, library
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

    def update_library_collections(
        self,
        library: Library,
        start_time: datetime,
        force_update_collection_map: Mapping,
        *,
        mark_library_in_progress=False,
    ) -> int:
        """Update timestamps for each collection for cover cache busting."""
        total_count = 0
        if mark_library_in_progress:
            library.start_update()
        status = UpdateCollectionTimestampsStatus()
        self.status_controller.start(status)
        try:
            log_list = []
            for model in COLLECTION_MODELS:
                count = self._update_collection_model(
                    force_update_collection_map, model, start_time, library, log_list
                )
                if not count:
                    continue
                self.log.debug(f"Updated {count} {model.__name__}s timestamps.")
                status.increment_complete(count)
                self.status_controller.update(status)
                total_count += count
        finally:
            if mark_library_in_progress:
                library.end_update()
            self.status_controller.finish(status)
        return total_count

    def update_collections(self, task) -> None:
        """Update collections in all libraries."""
        count = 0
        start_time = task.start_time or timezone.now()
        libraries = Library.objects.only("pk")
        for library in libraries:
            count += self.update_library_collections(
                library, start_time, {}, mark_library_in_progress=True
            )
        level = "INFO" if count else "DEBUG"
        self.log.log(level, f"Updated timestamps for {count} collections.")
        # All-libraries fan-out: ``mtime`` is the start of this update
        # pass so older mtime probes resolve correctly.
        self.librarian_queue.put(
            replace(LIBRARY_CHANGED_TASK, mtime=int(start_time.timestamp() * 1000))
        )
