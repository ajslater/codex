"""Update Collections timestamp for cover cache busting."""

from collections.abc import Mapping
from datetime import datetime

from django.db.models.functions.datetime import Now
from django.db.models.query_utils import Q
from django.utils import timezone

from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.status import UpdateCollectionTimestampsStatus
from codex.librarian.worker import WorkerStatusBase
from codex.models import StoryArc, Volume
from codex.models.collections import BrowserCollectionModel
from codex.models.library import Library
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE
from codex.views.const import COLLECTION_MODELS


class TimestampUpdater(WorkerStatusBase):
    """Update Collections timestamp for cover cache busting."""

    @staticmethod
    def _get_update_filter(
        model: type[BrowserCollectionModel],
        start_time: datetime,
        force_update_collection_map: Mapping,
        library: Library,
    ) -> Q:
        # Comic/CustomCover ``updated_at`` is stamped with the DB ``Now()``,
        # which SQLite stores at millisecond precision and *three* fractional
        # digits (e.g. ``…26.986``). ``start_time`` is a Python microsecond
        # datetime the ORM serialises with *six* digits (``…26.986605``).
        # SQLite compares these as TEXT, where ``"…26.986" < "…26.986605"``
        # (the shorter string is the prefix) — so a comic written in the same
        # second the import started is *excluded* by ``> start_time``. Its
        # collections then never get re-stamped and the browser's
        # ``library.changed`` mtime gate stays blind to a fast re-import such
        # as a tag write. Floor to the whole second so the bound is
        # ``…26.000000``, which orders correctly before every millisecond
        # value in that second. Over-including rows touched earlier in the
        # same second is harmless — at worst one extra (correct) reload.
        start_floor = start_time.replace(microsecond=0)

        # Get collections with comics updated during this import. A match
        # here implies the collection has children — no count needed.
        rel = "storyarcnumber__" if model == StoryArc else ""
        updated_at_rel = rel + "comic__updated_at__gt"
        library_rel = rel + "comic__library"
        updated_filter = {library_rel: library, updated_at_rel: start_floor}
        update_filter = Q(**updated_filter)

        # Get collections with custom covers updated during this import.
        # Only this branch can match an empty collection, so it carries
        # its own has-children join test. This used to be a
        # Count-aggregate filter over the whole OR — a per-row
        # GROUP BY join explosion costing ~1.5s per import.
        if model != Volume:
            update_filter |= Q(custom_cover__updated_at__gt=start_floor) & Q(
                **{rel + "comic__isnull": False}
            )

        # Get collections to be force updated (usually those with deleted
        # children). A force-updated collection (a comic moved or was
        # deleted OUT of it) must re-stamp even when it's now empty —
        # otherwise a viewer of the just-emptied collection never gets
        # the library.changed refresh. The empty row is reaped by the
        # janitor afterwards.
        if pks := force_update_collection_map.get(model):
            update_filter |= Q(pk__in=pks)

        return update_filter

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
        pks = tuple(
            model.objects.filter(update_filter).distinct().values_list("pk", flat=True)
        )
        count = len(pks)
        if count:
            # .update() can't run on a .distinct() queryset; route the
            # distinct pks back through a batched plain filter.
            for start in range(0, count, IMPORTER_LINK_FK_BATCH_SIZE):
                batch = pks[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
                model.objects.filter(pk__in=batch).update(updated_at=Now())
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
        # All-libraries fan-out: clients re-probe their viewed collection.
        self.librarian_queue.put(LIBRARY_CHANGED_TASK)
