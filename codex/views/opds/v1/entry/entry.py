"""OPDS v1 Entry."""
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from django.urls import reverse

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.opds.const import (
    AUTHOR_ROLES,
    BLANK_TITLE,
)
from codex.views.opds.util import (
    get_creator_people,
    get_m2m_objects,
)
from codex.views.opds.v1.entry.links import OPDS1EntryLinksMixin

LOG = get_logger(__name__)


class OPDS1Entry(OPDS1EntryLinksMixin):
    """An OPDS entry object."""

    _DATE_FORMAT_BASE = "%Y-%m-%dT%H:%M:%S"
    _DATE_FORMAT_MS = _DATE_FORMAT_BASE + ".%f%z"
    _DATE_FORMAT = _DATE_FORMAT_BASE + "%z"
    _DATE_FORMATS = (_DATE_FORMAT_MS, _DATE_FORMAT)

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
