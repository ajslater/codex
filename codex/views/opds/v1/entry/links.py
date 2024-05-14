"""OPDS v1 Entry Links Methods."""

from urllib.parse import quote_plus

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.views.const import MISSING_COVER_FN, MISSING_COVER_NAME_MAP
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

    def _thumb_link(self):
        if self.fake:
            return None
        cover_pk = getattr(self.obj, "cover_pk", None)
        if cover_pk:
            kwargs = {"pk": cover_pk}
            href = reverse("opds:bin:cover", kwargs=kwargs)
            mime_type = "image/webp"
        else:
            cover_name = MISSING_COVER_NAME_MAP.get(self.obj.group)
            cover_path = "img/"
            if cover_name:
                cover_path += cover_name + ".svg"
                mime_type = "image/svg+xml"
            else:
                cover_path += MISSING_COVER_FN
                mime_type = "image/webp"
            href = staticfiles_storage.url(cover_path)
        return OPDS1Link(Rel.THUMBNAIL, href, mime_type)

    def _image_link(self):
        if self.fake:
            return None
        cover_pk = getattr(self.obj, "cover_pk", None)
        if cover_pk:
            kwargs = {"pk": cover_pk, "page": 0}
            href = reverse("opds:bin:page", kwargs=kwargs)
            mime_type = "image/jpeg"
        else:
            fn = f"img/{MISSING_COVER_FN}"
            href = staticfiles_storage.url(fn)
            mime_type = "image/webp"
        return OPDS1Link(Rel.IMAGE, href, mime_type)

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

        thr_count = 0 if self.fake else self.obj.child_count
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
        count = max(self.obj.page_count, 1)
        bookmark_updated_at = self.obj.bookmark_updated_at
        return OPDS1Link(
            Rel.STREAM,
            href,
            MimeType.STREAM,
            pse_count=count,
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
            if thumb := self._thumb_link():
                result += [thumb]
            if image := self._image_link():
                result += [image]

            if self.obj.group == "c" and not self.fake:
                result += self._links_comic()
            elif nav := self._nav_link():
                result += [nav]

        except Exception:
            msg = f"Getting entry links for {self.obj}"
            LOG.exception(msg)
        return result
