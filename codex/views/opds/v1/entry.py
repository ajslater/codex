"""OPDS Entry."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.opds.const import (
    AUTHOR_ROLES,
    BLANK_TITLE,
    MimeType,
    Rel,
)
from codex.views.opds.util import (
    get_creator_people,
    get_m2m_objects,
    update_href_query_params,
)
from codex.views.opds.v1.const import OPDSLink

LOG = get_logger(__name__)


@dataclass
class OPDS1EntryObject:
    """Fake entry db object for top link & facet entries."""

    group: str = ""
    pk: int = 0
    name: str = ""
    summary: str = ""
    fake: bool = True


class OPDS1Entry:
    """An OPDS entry object."""

    _DATE_FORMAT_BASE = "%Y-%m-%dT%H:%M:%S"
    _DATE_FORMAT_MS = _DATE_FORMAT_BASE + ".%f%z"
    _DATE_FORMAT = _DATE_FORMAT_BASE + "%z"
    _DATE_FORMATS = (_DATE_FORMAT_MS, _DATE_FORMAT)

    def __init__(self, obj, query_params, extra_data):
        """Initialize params."""
        self.obj = obj
        self.fake = isinstance(self.obj, OPDS1EntryObject)
        self.query_params = query_params
        self.acquision_groups, self.issue_max, self.metadata = extra_data

    @property
    def id_tag(self):
        """GUID is a nav url."""
        # Id top links by query params but not regular entries.
        return self._nav_href(metadata=self.metadata)

    @property
    def title(self):
        """Compute the item title."""
        result = ""
        try:
            parts = []
            if not self.fake:
                group = self.obj.group
                if group == "i":
                    parts.append(self.obj.publisher_name)
                elif group == "v":
                    parts.append(self.obj.series_name)
                elif group == "c":
                    title = Comic.get_title(self.obj, issue_max=self.issue_max)
                    parts.append(title)

            if name := self.obj.name:
                parts.append(name)

            result = " ".join(filter(None, parts))
        except Exception as exc:
            LOG.exception(exc)

        if not result:
            result = BLANK_TITLE
        return result

    @property
    def issued(self):
        """Return the published date."""
        if self.obj.group == "c":
            return self.obj.date
        return None

    @property
    def publisher(self):
        """Return the publisher."""
        return self.obj.publisher_name

    def _get_datefield(self, key):
        result = None
        if not self.fake and (value := getattr(self.obj, key, None)):
            for date_format in self._DATE_FORMATS:
                try:
                    if isinstance(value, str):
                        result = datetime.strptime(value, date_format).astimezone(
                            timezone.utc
                        )
                    if isinstance(value, datetime):
                        result = value.astimezone(timezone.utc).strftime(date_format)
                    break
                except ValueError:
                    pass
        return result

    @property
    def updated(self):
        """When the entry was last updated."""
        return self._get_datefield("updated_at")

    @property
    def published(self):
        """When the entry was created."""
        return self._get_datefield("created_at")

    @property
    def language(self):
        """Return the entry language."""
        return self.obj.language

    @property
    def summary(self):
        """Return a child count or comic summary."""
        if self.obj.group == "c":
            desc = self.obj.summary
        else:
            children = self.obj.child_count
            desc = f"{children} issues"
        return desc

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
        return OPDSLink(Rel.THUMBNAIL, href, "image/webp")

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
        return OPDSLink(Rel.IMAGE, href, mime_type)

    def _nav_href(self, metadata=False):
        kwargs = {"group": self.obj.group, "pk": self.obj.pk, "page": 1}
        href = reverse("opds:v1:feed", kwargs=kwargs)
        qps = {}
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

        return OPDSLink(rel, href, mime_type, thr_count=thr_count)

    def _download_link(self):
        pk = self.obj.pk
        if not pk:
            return None
        fn = Comic.get_filename(self.obj)
        fn = quote_plus(fn)
        kwargs = {"pk": pk, "filename": fn}
        href = reverse("opds:bin:download", kwargs=kwargs)
        return OPDSLink(Rel.ACQUISITION, href, MimeType.DOWNLOAD, length=self.obj.size)

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
        return OPDSLink(
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

    @staticmethod
    def _add_url_to_obj(objs, filter_key):
        """Add filter urls to objects."""
        kwargs = {"group": "s", "pk": 0, "page": 1}
        url_base = reverse("opds:v1:feed", kwargs=kwargs)
        result = []
        for obj in objs:
            qp = {"filters": json.dumps({filter_key: [obj.pk]})}
            qp = urlencode(qp)
            obj.url = url_base + "?" + qp
            result.append(obj)
        return result

    @property
    def authors(self):
        """Get Author names."""
        if not self.metadata:
            return []
        people = get_creator_people(self.obj.pk, AUTHOR_ROLES)
        return self._add_url_to_obj(people, "creators")

    @property
    def contributors(self):
        """Get Contributor names."""
        if not self.metadata:
            return []
        people = get_creator_people(self.obj.pk, AUTHOR_ROLES, exclude=True)
        return self._add_url_to_obj(people, "creators")

    @property
    def category_groups(self):
        """Get Category labels."""
        if not self.metadata:
            return {}
        return get_m2m_objects(self.obj.pk)
