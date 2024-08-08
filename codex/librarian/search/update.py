"""Search Index update."""

import re
from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.db.models.aggregates import Max
from django.db.models.functions.datetime import Now
from django.template import Context, Template
from humanize import naturaldelta

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexRemoveStaleTask
from codex.models import Comic, Library
from codex.models.comic import ComicFTS
from codex.settings.settings import CODEX_PATH, CPU_MULTIPLIER
from codex.status import Status

TEMPLATE_PATH = CODEX_PATH / "templates/search/indexes/codex/fts.html"
with TEMPLATE_PATH.open("r") as f:
    SEARCH_TEMPLATE = Template(f.read())

REPLACE_WHITESPACE_RE = re.compile(r"\s+")


class FTSUpdateMixin(RemoveMixin):
    """Search Index update methods."""

    _STATUS_FINISH_TYPES = (
        SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    )
    _MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    _MIN_BATCH_SIZE = 1
    # A larger batch size might be slightly faster for very large
    # indexes and require less optimization later, but steady progress
    # updates are better UX.
    _MAX_BATCH_SIZE = 640
    _EXPECTED_EXCEPTIONS = (
        DatabaseError,
        IndexError,
        ObjectDoesNotExist,
    )
    _MAX_RETRIES = 8
    _CPU_MULTIPLIER = CPU_MULTIPLIER
    _UPDATE_SORT_BY = ("-updated_at",)

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE)]
        if not rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
        self.status_controller.start_many(statii)

    COMICFTS_UPDATE_FIELDS = ("body", "updated_at")

    def _update_search_index(self, start_time, rebuild):
        """Update or Rebuild the search index."""
        remove_stale = False
        any_update_in_progress = Library.objects.filter(
            covers_only=False, update_in_progress=True
        ).exists()
        if any_update_in_progress:
            self.log.debug(
                "Database update in progress, not updating search index yet."
            )
            return remove_stale

        # if not rebuild and not self.is_search_index_uuid_match():
        #    rebuild = True

        self._init_statuses(rebuild)

        # Clear
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()

        all_comic_fts_comics = ComicFTS.objects.values_list("comic__pk", flat=True)
        missing_comics = Comic.objects.exclude(pk__in=all_comic_fts_comics)
        create_comicfts = []
        for comic in missing_comics:
            context = Context({"comic": comic})
            body = SEARCH_TEMPLATE.render(context)
            body = REPLACE_WHITESPACE_RE.sub(" ", body)
            now = Now()
            comicfts = ComicFTS(
                comic_id=comic.pk, body=body, updated_at=now, created_at=now
            )
            create_comicfts.append(comicfts)

        ComicFTS.objects.bulk_create(create_comicfts)
        count = len(create_comicfts)
        self.log.info(f"Created {count} search entries.")

        fts_watermark = ComicFTS.objects.aggregate(max=Max("updated_at"))["max"]
        out_of_date_comics = Comic.objects.filter(
            updated_at__gt=fts_watermark, pk__in=all_comic_fts_comics
        )
        update_comicfts = []
        for comic in out_of_date_comics:
            context = Context({"comic": comic})
            body = SEARCH_TEMPLATE.render(context)
            body = REPLACE_WHITESPACE_RE.sub(" ", body)
            comicfts = ComicFTS(comic_id=comic.pk, body=body, updated_at=Now())
            update_comicfts.append(comicfts)

        ComicFTS.objects.bulk_update(update_comicfts, self.COMICFTS_UPDATE_FIELDS)
        count = len(update_comicfts)
        self.log.info(f"Updated {count} search entries.")

        if remove_stale:
            self.remove_stale_records()

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        self.log.info(f"Search index updated in {elapsed}.")
        return remove_stale

    def update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start_time = time()
        self.abort_event.clear()
        remove_stale = False
        try:
            remove_stale = self._update_search_index(start_time, rebuild)
        except Exception:
            self.log.exception("Update search index")
        finally:
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES)
            if remove_stale:
                task = SearchIndexRemoveStaleTask()
                self.librarian_queue.put(task)
