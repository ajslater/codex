"""OPDS v1 Entry Links Methods."""

from urllib.parse import quote_plus

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from codex.models import Comic
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.data import OPDS1Link
from codex.views.opds.v1.entry.data import OPDS1EntryData, OPDS1EntryObject


class OPDS1EntryLinksMixin:
    """OPDS v1 Entry Links Methods."""

    def __init__(self, obj, query_params, data: OPDS1EntryData):
        """Initialize params."""
        self.obj = obj
        self.fake = isinstance(self.obj, OPDS1EntryObject)
        self.query_params = query_params
        self.acquision_groups = data.acquisition_groups
        self.issue_number_max = data.issue_number_max
        self.metadata = data.metadata
        self.mime_type_map = data.mime_type_map

    def _thumb_link(self):
        if self.fake:
            return None
        cover_pk = self.obj.cover_pk
        if cover_pk:
            kwargs = {"pk": cover_pk}
            href = reverse("opds:bin:cover", kwargs=kwargs)
        elif cover_pk == 0:
            href = staticfiles_storage.url("img/missing_cover.webp")
        else:
            return None
        return OPDS1Link(Rel.THUMBNAIL, href, "image/webp")

    def _image_link(self):
        if self.fake:
            return None
        cover_pk = self.obj.cover_pk
        if cover_pk:
            kwargs = {"pk": cover_pk, "page": 0}
            href = reverse("opds:bin:page", kwargs=kwargs)
            mime_type = "image/jpeg"
        elif cover_pk == 0:
            href = staticfiles_storage.url("img/missing_cover.webp")
            mime_type = "image/webp"
        else:
            return None
        return OPDS1Link(Rel.IMAGE, href, mime_type)

    def _nav_href(self, metadata=False):
        kwargs = {"group": self.obj.group, "pk": self.obj.pk, "page": 1}
        href = reverse("opds:v1:feed", kwargs=kwargs)
        qps = {}
        if (
            self.obj.group == "a"
            and self.obj.pk
            and not self.query_params.get("orderBy")
        ):
            # story arcs get ordered by story_arc_number by default
            qps.update({"orderBy": "story_arc_number"})
        if metadata:
            qps.update({"opdsMetadata": 1})
        return update_href_query_params(href, self.query_params, qps)

    def _nav_link(self, metadata=False):
        group = self.obj.group

        if group in self.acquision_groups:
            mime_type = MimeType.ENTRY_CATALOG if metadata else MimeType.ACQUISITION
        else:
            mime_type = MimeType.NAV

        href = self._nav_href(metadata)
        thr_count = 0 if self.fake else self.obj.child_count
        rel = Rel.ALTERNATE if metadata else "subsection"

        return OPDS1Link(rel, href, mime_type, thr_count=thr_count)

    def _download_link(self):
        pk = self.obj.pk
        if not pk:
            return None
        fn = Comic.get_filename(self.obj)
        fn = quote_plus(fn)
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
        count = self.obj.page_count
        bookmark_updated_at = self.obj.bookmark_updated_at
        return OPDS1Link(
            Rel.STREAM,
            href,
            MimeType.STREAM,
            pse_count=count,
            pse_last_read=page,
            pse_last_read_date=bookmark_updated_at,
        )

    @property
    def links(self):
        """Create all entry links."""
        result = []
        if thumb := self._thumb_link():
            result += [thumb]
        if image := self._image_link():
            result += [image]

        if self.obj.group == "c" and not self.fake:
            if download := self._download_link():
                result += [download]
            if stream := self._stream_link():
                result += [stream]
            if not self.metadata and (metadata := self._nav_link(metadata=True)):
                result += [metadata]
        elif nav := self._nav_link():
            result += [nav]

        return result
