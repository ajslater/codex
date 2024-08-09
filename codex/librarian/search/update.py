"""Search Index update."""

import re
from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from django.db.models.aggregates import Max
from django.db.models.expressions import F
from django.db.models.functions.datetime import Now
from django.template import Context, Template
from humanize import naturaldelta

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.models import Comic, Library
from codex.models.comic import ComicFTS
from codex.settings.settings import CODEX_PATH
from codex.status import Status

_TEMPLATE_PATH = CODEX_PATH / "templates/search/comic.html"
with _TEMPLATE_PATH.open("r") as f:
    _SEARCH_TEMPLATE = Template(f.read())

_REPLACE_WHITESPACE_RE = re.compile(r"\s+")
_COMICFTS_UPDATE_FIELDS = ("body", "updated_at")
_MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))


class FTSUpdateMixin(RemoveMixin):
    """Search Index update methods."""

    _STATUS_FINISH_TYPES = (
        SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    )

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE)]
        if not rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
        self.status_controller.start_many(statii)

    def _update_search_index_clean(self, rebuild):
        """Clear or clean the search index."""
        if rebuild:
            self.log.info("Rebuilding search index...")
            self.clear_search_index()
        else:
            self.remove_stale_records()

    @staticmethod
    def _create_fts_body(comic):
        """Create an FTS body row from the template."""
        context = Context({"comic": comic})
        body = _SEARCH_TEMPLATE.render(context)
        return _REPLACE_WHITESPACE_RE.sub(" ", body)

    def _update_search_index_create(self):
        """Create missing search entries."""
        missing_comics = Comic.objects.filter(comicfts__isnull=True)
        create_comicfts = []
        for comic in missing_comics:
            body = self._create_fts_body(comic)
            now = Now()
            comicfts = ComicFTS(
                comic_id=comic.pk, body=body, updated_at=now, created_at=now
            )
            create_comicfts.append(comicfts)

        ComicFTS.objects.bulk_create(create_comicfts)
        count = len(create_comicfts)
        if count:
            self.log.info(f"Created {count} search entries.")
        else:
            self.log.debug("Created no search entries.")

    def _update_search_index_update(self):
        """Update out of date search entries."""
        out_of_date_comics = Comic.objects.alias(
            fts_watermark=Max("comicfts__updated_at", default=_MIN_UTC_DATE)
        ).filter(updated_at__gt=F("fts_watermark"))
        update_comicfts = []
        for comic in out_of_date_comics:
            body = self._create_fts_body(comic)
            now = Now()
            comicfts = ComicFTS(comic_id=comic.pk, body=body, updated_at=now)
            update_comicfts.append(comicfts)

        ComicFTS.objects.bulk_update(update_comicfts, _COMICFTS_UPDATE_FIELDS)
        count = len(update_comicfts)
        if count:
            self.log.info(f"Updated {count} search entries.")
        else:
            self.log.debug("Updated no search entries.")

    def _update_search_index(self, start_time, rebuild):
        """Update or Rebuild the search index."""
        any_update_in_progress = Library.objects.filter(
            covers_only=False, update_in_progress=True
        ).exists()
        if any_update_in_progress:
            self.log.debug(
                "Database update in progress, not updating search index yet."
            )
            return

        self._init_statuses(rebuild)

        self._update_search_index_clean(rebuild)
        self._update_search_index_create()
        self._update_search_index_update()

        elapsed_time = time() - start_time
        elapsed = naturaldelta(elapsed_time)
        self.log.info(f"Search index updated in {elapsed}.")

    def update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start_time = time()
        self.abort_event.clear()
        try:
            self._update_search_index(start_time, rebuild)
        except Exception:
            self.log.exception("Update search index")
        finally:
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES)
