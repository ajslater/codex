"""OPDS v1 Entry Links Methods."""

from datetime import datetime
from math import floor
from urllib.parse import quote_plus

from comicbox.box import Comicbox
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.data import OPDS1Link
from codex.views.opds.v1.entry.data import OPDS1EntryData, OPDS1EntryObject

LOG = get_logger(__name__)


class OPDS1EntryLinksMixin:
    """OPDS v1 Entry Links Methods."""

    def __init__(
        self, obj, query_params, data: OPDS1EntryData, title_filename_fallback=False
    ):
        """Initialize params."""
        self.obj = obj
        self.fake = isinstance(self.obj, OPDS1EntryObject)
        self.query_params = query_params
        self.acquision_groups = data.acquisition_groups
        self.zero_pad = data.zero_pad
        self.metadata = data.metadata
        self.mime_type_map = data.mime_type_map
        self.title_filename_fallback = title_filename_fallback

    def _cover_link(self, rel):
        if self.fake:
            return None
        # cover_pk = getattr(self.obj, "cover_pk", None)
        try:
            kwargs = {"group": self.obj.group, "pks": self.obj.ids}
            ts = floor(datetime.timestamp(self.obj.updated_at))
            query_params = {
                "customCovers": True,
                "dynamicCovers": False,
                "ts": ts,
            }
            href = reverse("opds:bin:cover", kwargs=kwargs)
            href = update_href_query_params(href, query_params)
            mime_type = "image/webp"
            return OPDS1Link(rel, href, mime_type)
        except Exception:
            LOG.exception("create thumb")

    def _nav_href(self, metadata=False):
        try:
            pks = sorted(self.obj.ids)
            kwargs = {"group": self.obj.group, "pks": pks, "page": 1}
            href = reverse("opds:v1:feed", kwargs=kwargs)
            qps = {}
            if (
                self.obj.group == "a"
                and self.obj.ids
                and 0 not in self.obj.ids
                and not self.query_params.get("orderBy")
            ):
                # story arcs get ordered by story_arc_number by default
                qps.update({"orderBy": "story_arc_number"})
            if metadata:
                qps.update({"opdsMetadata": 1})
            return update_href_query_params(href, self.query_params, qps)
        except Exception:
            msg = f"creating nav href for entry {self.obj}"
            LOG.exception(msg)
            raise

    def _nav_link(self, metadata=False):
        href = self._nav_href(metadata)

        group = self.obj.group
        if group in self.acquision_groups:
            mime_type = MimeType.ENTRY_CATALOG if metadata else MimeType.ACQUISITION
        else:
            mime_type = MimeType.NAV

        thr_count = (
            0 if self.fake else 1 if self.obj.group == "c" else self.obj.child_count
        )
        rel = Rel.ALTERNATE if metadata else "subsection"

        return OPDS1Link(rel, href, mime_type, thr_count=thr_count)

    def _download_link(self):
        pk = self.obj.pk
        if not pk:
            return None
        fn = quote_plus(self.obj.get_filename())
        kwargs = {"pk": pk, "filename": fn}
        href = reverse("opds:bin:download", kwargs=kwargs)
        mime_type = self.mime_type_map.get(self.obj.file_type, MimeType.OCTET)
        return OPDS1Link(Rel.ACQUISITION, href, mime_type, length=self.obj.size)

    def lazy_metadata(self):
        """Get barebones metadata lazily to make pse work for chunky-like readers."""
        if self.obj.page_count and self.obj.file_type:
            return False
        with Comicbox(self.obj.path) as cb:
            self.obj.page_count = cb.get_page_count()
            self.obj.file_type = cb.get_file_type()
        LOG.debug(f"Got lazy opds pse metadata for {self.obj.path}")
        return True

    def _stream_link(self):
        pk = self.obj.pk
        if not pk:
            return None
        kwargs = {"pk": pk, "page": 0}
        qps = {"bookmark": 1}
        href = reverse("opds:bin:page", kwargs=kwargs)
        href = update_href_query_params(href, {}, qps)
        href = href.replace("0/page.jpg", "{pageNumber}/page.jpg")
        page = self.obj.page
        # extra stupid pse chunky fix for no metadata
        self.lazy_metadata()
        pse_count = self.obj.page_count
        bookmark_updated_at = self.obj.bookmark_updated_at
        return OPDS1Link(
            Rel.STREAM,
            href,
            MimeType.STREAM,
            pse_count=pse_count,
            pse_last_read=page,
            pse_last_read_date=bookmark_updated_at,
        )

    def _links_comic(self):
        """Links for comics."""
        result = []
        if download := self._download_link():
            result += [download]
        if stream := self._stream_link():
            result += [stream]
        if not self.metadata and (metadata := self._nav_link(metadata=True)):
            result += [metadata]
        return result

    @property
    def links(self):
        """Create all entry links."""
        result = []
        try:
            if thumb := self._cover_link(Rel.THUMBNAIL):
                result += [thumb]
            if image := self._cover_link(Rel.IMAGE):
                result += [image]

            if self.obj.group == "c" and not self.fake:
                result += self._links_comic()
            elif nav := self._nav_link():
                result += [nav]

        except Exception:
            msg = f"Getting entry links for {self.obj}"
            LOG.exception(msg)
        return result
