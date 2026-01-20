"""OPDS v1 Entry."""

import json
from contextlib import suppress
from datetime import datetime, timezone

from dateutil import parser
from django.urls import reverse
from loguru import logger

from codex.models import Comic
from codex.views.opds.const import (
    AUTHOR_ROLES,
    BLANK_TITLE,
    TopRoutes,
)
from codex.views.opds.util import (
    get_credit_people,
    get_m2m_objects,
)
from codex.views.opds.v1.entry.links import OPDS1EntryLinksMixin


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
                        volume=True,
                        name=True,
                        filename_fallback=self.title_filename_fallback,
                        zero_pad=self.zero_pad,
                    )
                    parts.append(title)

            if group != "c" and (name := self.obj.name):
                parts.append(name)

            result = " ".join(filter(None, parts))
        except Exception:
            logger.exception("Getting OPDS1 title")

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
        result = []
        for obj in objs:
            filters = json.dumps({filter_key: [obj.pk]})
            query = {"filters": filters}
            obj.url = reverse(
                "opds:v1:feed", kwargs=dict(TopRoutes.SERIES), query=query
            )
            result.append(obj)
        return result

    @property
    def authors(self):
        """Get Author names."""
        if not self.metadata:
            return []
        people = get_credit_people(self.obj.ids, AUTHOR_ROLES, exclude=False)
        return self._add_url_to_obj(people, "credits")

    @property
    def contributors(self):
        """Get Credit names."""
        if not self.metadata:
            return []
        people = get_credit_people(self.obj.ids, AUTHOR_ROLES, exclude=True)
        return self._add_url_to_obj(people, "credits")

    @property
    def category_groups(self):
        """Get Category labels."""
        if not self.metadata:
            return {}
        return get_m2m_objects(self.obj.ids)
