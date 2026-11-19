"""OPDS v2 subject links filter the feed, an arc's by its reading list."""

import json
from typing import Final, override
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import ReadingList, SeriesGroup
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


class OPDSSubjectLinkTests(ReadingListFixture):
    """A subject's link names a filter the feed applies."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        self.client.force_login(User.objects.create_user(username="u", password=_PW))
        c1 = self.comics[0]
        self.tag(c1, "Civil War", 1)
        sync_tag_lists()
        group = SeriesGroup.objects.create(name="Events")
        c1.series_groups.add(group)

    def _subjects(self) -> dict[str, dict]:
        cache.clear()
        response = self.client.get(f"/opds/v2.0/c/{self.comics[0].pk}/1", follow=True)
        assert response.status_code == _OK, response.content[:300]
        metadata = json.loads(response.content)["metadata"]
        return {subject["name"]: subject for subject in metadata.get("subject", ())}

    @staticmethod
    def _filters(subject: dict) -> dict:
        href = subject["links"][0]["href"]
        query = parse_qs(urlsplit(href).query)
        return json.loads(query["filters"][0])

    def test_an_arc_links_to_its_reading_list(self) -> None:
        """The arc's subject filters by the arc's list, not a dropped key."""
        civil_war = ReadingList.objects.get(name="Civil War")
        filters = self._filters(self._subjects()["Civil War"])
        assert filters == {"reading_lists": [civil_war.pk]}

    def test_a_series_group_link_uses_its_filter_key(self) -> None:
        """Series groups filter under ``series_groups``, not ``seriesgroups``."""
        filters = self._filters(self._subjects()["Events"])
        assert list(filters) == ["series_groups"]

    def test_the_arc_link_filters_the_feed(self) -> None:
        """Following the link lists the arc's comic."""
        href = self._subjects()["Civil War"]["links"][0]["href"]
        cache.clear()
        response = self.client.get(href, follow=True)
        assert response.status_code == _OK, response.content[:300]
        feed = json.loads(response.content)
        titles = [
            pub["metadata"]["title"]
            for group in [feed, *feed.get("groups", [])]
            for pub in group.get("publications", ())
        ]
        assert titles == ["Civil War (2006) #1"], titles
