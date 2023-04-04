"""OPDS Entry."""
import math
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote_plus

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.opds_v1.util import (
    BLANK_TITLE,
    FALSY,
    MimeType,
    OPDSLink,
    Rel,
    update_href_query_params,
)

LOG = get_logger(__name__)


class OPDSEntry:
    """An OPDS entry object."""

    _DATE_FORMAT_BASE = "%Y-%m-%dT%H:%M:%S"
    DATE_FORMAT_MS = _DATE_FORMAT_BASE + ".%f%z"
    DATE_FORMAT = _DATE_FORMAT_BASE + "%z"
    DATE_FORMATS = (DATE_FORMAT_MS, DATE_FORMAT)
    CATEGORY_KEYS = (
        "characters",
        "genres",
        "locations",
        "series_groups",
        "story_arcs",
        "tags",
        "teams",
    )

    def __init__(self, obj, acquisition_groups, query_params):
        """Initialize params."""
        self.obj = obj
        self.acquision_groups = acquisition_groups
        self.query_params = query_params

    @staticmethod
    def _compute_zero_pad(issue_max):
        """Compute zero padding for issues."""
        if not issue_max or issue_max < 1:
            return 1
        return math.floor(math.log10(issue_max)) + 1

    @property
    def id_tag(self):
        """GUID is a nav url."""
        try:
            metadata = self.query_params.get("opdsMetadata", "").lower() not in FALSY
            # Id top links by query params but not regular entries.
            return self._nav_href(metadata=metadata)
        except Exception as exc:
            LOG.exception(exc)

    @property
    def title(self):
        """Compute the item title."""
        result = ""
        try:
            group = self.obj.get("group")
            parts = []
            if group == "i":
                parts.append(self.obj.get("publisher_name"))
            elif group == "v":
                parts.append(self.obj.get("series_name"))
            elif group == "c":
                parts.append(self.obj.get("series_name"))

                issue_max = self.obj.get("issue_max")
                zero_pad = self._compute_zero_pad(issue_max)
                issue = self.obj.get("issue")
                if issue is None:
                    issue = Decimal(0)
                issue = issue.normalize()
                issue_suffix = self.obj.get("issue_suffix", "")

                int_issue = math.floor(issue)
                if issue == int_issue:
                    issue_str = str(int_issue)
                else:
                    issue_str = str(issue)
                    decimal_parts = issue_str.split(".")
                    if len(decimal_parts) > 1:
                        zero_pad += len(decimal_parts[1]) + 1

                issue_num = issue_str.zfill(zero_pad)
                full_issue_str = f"#{issue_num}{issue_suffix}"
                parts.append(full_issue_str)

            if name := self.obj.get("name"):
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
        try:
            return self.obj.get("date")
        except Exception as exc:
            LOG.exception(exc)

    @property
    def publisher(self):
        """Return the publisher."""
        return self.obj.get("publisher_name")

    def _get_datefield(self, key):
        try:
            if value := self.obj.get(key):
                result = None
                for date_format in self.DATE_FORMATS:
                    try:
                        result = datetime.strptime(value, date_format).astimezone(
                            timezone.utc
                        )
                        break
                    except ValueError:
                        pass
                return result
        except Exception as exc:
            LOG.warning(exc)

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
        return self.obj.get("language")

    @property
    def summary(self):
        """Return a child count or comic summary."""
        try:
            desc = self.obj.get("summary")
            if not desc and (children := self.obj.get("child_count")):
                desc = f"{children} issues"
        except Exception:
            LOG.exception("get summary")
        else:
            return desc

    def _thumb_link(self):
        cover_pk = self.obj.get("cover_pk")
        if cover_pk:
            kwargs = {"pk": cover_pk}
            href = reverse("opds:v1:cover", kwargs=kwargs)
        elif cover_pk == 0:
            href = staticfiles_storage.url("img/missing_cover.webp")
        else:
            return None
        return OPDSLink(Rel.THUMBNAIL, href, "image/webp")

    def _image_link(self):
        cover_pk = self.obj.get("cover_pk")
        if cover_pk:
            kwargs = {"pk": cover_pk, "page": 0}
            href = reverse("opds:v1:page", kwargs=kwargs)
            mime_type = "image/jpeg"
        elif cover_pk == 0:
            href = staticfiles_storage.url("img/missing_cover.webp")
            mime_type = "image/webp"
        else:
            return None
        return OPDSLink(Rel.IMAGE, href, mime_type)

    def _nav_href(self, metadata=False):
        group = self.obj.get("group")
        pk = self.obj.get("pk")
        kwargs = {"group": group, "pk": pk, "page": 1}
        href = reverse("opds:v1:browser", kwargs=kwargs)
        qps = {} if group == "c" else self.obj.get("query_params", {})

        if metadata:
            qps.update({"opdsMetadata": 1})
        return update_href_query_params(href, self.query_params, qps)

    def _nav_link(self, metadata=False):
        group = self.obj.get("group")

        if group in self.acquision_groups:
            mime_type = MimeType.ENTRY_CATALOG if metadata else MimeType.ACQUISITION
        else:
            mime_type = MimeType.NAV

        href = self._nav_href(metadata)
        thr_count = self.obj.get("child_count")
        rel = Rel.ALTERNATE if metadata else self.obj.get("nav_link_rel", "subsection")

        return OPDSLink(rel, href, mime_type, thr_count=thr_count)

    def _download_link(self):
        pk = self.obj.get("pk")
        if not pk:
            return None
        fn = Comic.get_filename(self.obj)
        fn = quote_plus(fn)
        kwargs = {"pk": pk, "filename": fn}
        href = reverse("opds:v1:download", kwargs=kwargs)
        return OPDSLink(
            Rel.ACQUISITION,
            href,
            MimeType.DOWNLOAD,
            length=self.obj.get("size", 1),
        )

    def _stream_link(self):
        pk = self.obj.get("pk")
        if not pk:
            return None
        base_url = reverse("opds:v1:start")
        href = f"{base_url}c/{pk}/"
        href += "{pageNumber}/page.jpg?bookmark=1"
        count = self.obj.get("page_count")
        page = self.obj.get("page", 0)
        bookmark_updated_at = self.obj.get("bookmark_updated_at")
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

        if self.obj.get("group") == "c":
            if download := self._download_link():
                result += [download]
            if stream := self._stream_link():
                result += [stream]
            if (
                not self.query_params.get("opdsMetadata", "").lower() not in FALSY
            ) and (metadata := self._nav_link(metadata=True)):
                result += [metadata]
        elif nav := self._nav_link():
            result += [nav]

        return result

    def _parse_csv_fields(self, keys):
        """Parse hacky csv field annotation."""
        names = set()
        try:
            for key in keys:
                if val := self.obj.get(key):
                    names |= set(val.split(","))
        except Exception as exc:
            LOG.exception(exc)
        return names

    @property
    def authors(self):
        """Get Author names."""
        return self._parse_csv_fields(("authors",))

    @property
    def contributors(self):
        """Get Contributor names."""
        return self._parse_csv_fields(("contributors",))

    @property
    def categories(self):
        """Get Category labels."""
        return self._parse_csv_fields(self.CATEGORY_KEYS)
