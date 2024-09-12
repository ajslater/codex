"""OPDS v1 Entry."""

import json
from contextlib import suppress
from datetime import datetime, timezone
from urllib.parse import urlencode

from dateutil import parser
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.opds.const import (
    AUTHOR_ROLES,
    BLANK_TITLE,
)
from codex.views.opds.util import (
    get_contributor_people,
    get_m2m_objects,
)
from codex.views.opds.v1.entry.links import OPDS1EntryLinksMixin

LOG = get_logger(__name__)


class OPDS1Entry(OPDS1EntryLinksMixin):
    """An OPDS entry object."""

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
            group = self.obj.group
            if not self.fake:
                if group == "i":
                    parts.append(self.obj.publisher_name)
                elif group == "v":
                    parts.append(self.obj.series_name)
                elif group == "c":
                    title = Comic.get_title(
                        self.obj,
                        zero_pad=self.zero_pad,
                        filename_fallback=self.title_filename_fallback,
                    )
                    parts.append(title)

            if group != "c" and (name := self.obj.name):
                parts.append(name)

            result = " ".join(filter(None, parts))
        except Exception:
            LOG.exception("Getting OPDS1 title")

        if not result:
            result = BLANK_TITLE
        return result

    @property
    def issued(self):
        """Return the published date."""
        date = ""
        if self.obj.group == "c":
            with suppress(Exception):
                date = self.obj.date.isoformat()

        return date

    @property
    def publisher(self):
        """Return the publisher."""
        return self.obj.publisher_name

    def _get_datefield(self, key):
        result = None
        if not self.fake and (value := getattr(self.obj, key, None)):
            try:
                if isinstance(value, str):
                    result = parser.parse(value)
                if isinstance(value, datetime):
                    result = value.astimezone(timezone.utc).isoformat()
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
        kwargs = {"group": "s", "pks": {}, "page": 1}
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
        people = get_contributor_people(self.obj.ids, AUTHOR_ROLES)
        return self._add_url_to_obj(people, "contributors")

    @property
    def contributors(self):
        """Get Contributor names."""
        if not self.metadata:
            return []
        people = get_contributor_people(self.obj.ids, AUTHOR_ROLES, exclude=True)
        return self._add_url_to_obj(people, "contributors")

    @property
    def category_groups(self):
        """Get Category labels."""
        if not self.metadata:
            return {}
        return get_m2m_objects(self.obj.ids)
