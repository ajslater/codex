"""
OPDS v1 entry credit emission.

Codex splits a comic's credits by role: people in ``AUTHOR_ROLES`` become
Atom ``<author>`` elements, everyone else becomes ``<contributor>``.
Both only appear on metadata feeds (``?opdsMetadata=1``), which is why
the base feed fixtures never exercised them.
"""

import xml.etree.ElementTree as ET
from typing import Final, override

from django.core.cache import cache
from django.test import TestCase

from codex.models import Comic, Credit, CreditPerson, CreditRole, Series
from tests.test_opds_feed import (
    _HTTP_OK,
    _V1_START,
    _OPDSFixtureMixin,
)

# "Writer" is in AUTHOR_ROLES, "Colorist" is not, so one person lands in
# each bucket and the two elements can be told apart.
_AUTHOR_NAME: Final = "Jane Writer"
_CONTRIBUTOR_NAME: Final = "Cole Orist"


def _local_name(tag: str) -> str:
    """Strip any XML namespace from a tag."""
    return tag.rsplit("}", 1)[-1]


def _person_names(content: bytes, element: str) -> set[str]:
    """Every ``<name>`` under the named person element in any entry."""
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    return {
        (name.text or "").strip()
        for el in root.iter()
        if _local_name(el.tag) == element
        for name in el
        if _local_name(name.tag) == "name"
    }


class OPDSv1ContributorTestCase(_OPDSFixtureMixin, TestCase):
    """Entry credits reach the feed, split by role."""

    @override
    def setUp(self) -> None:
        """Give every comic one author-role and one other-role credit."""
        super().setUp()
        writer = Credit.objects.create(
            person=CreditPerson.objects.create(name=_AUTHOR_NAME),
            role=CreditRole.objects.create(name="Writer"),
        )
        colorist = Credit.objects.create(
            person=CreditPerson.objects.create(name=_CONTRIBUTOR_NAME),
            role=CreditRole.objects.create(name="Colorist"),
        )
        for comic in Comic.objects.all():
            comic.credits.add(writer, colorist)
        series = Series.objects.order_by("pk").first()
        assert series
        # An acquisition feed: the entries are comics, so they carry
        # credits. Metadata is opt-in, and both credit properties
        # short-circuit to [] without it.
        self.feed = f"{_V1_START}series/{series.pk}?opdsMetadata=1"  # pyright: ignore[reportUninitializedInstanceVariable]
        # Browser feeds go through cachalot; clear so the new rows surface.
        cache.clear()

    def test_authors_and_contributors_both_render(self) -> None:
        """Author-role and other-role credits each reach their element."""
        response = self.client.get(self.feed)
        assert response.status_code == _HTTP_OK

        # <author> has always worked: the serializer field, the entry
        # property and the template all agree on the name. <contributor>
        # is the regression -- the serializer called it "credits", which
        # matches nothing on the entry, so DRF dropped it and the
        # template's contributor loop silently iterated nothing.
        assert _person_names(response.content, "author") == {_AUTHOR_NAME}
        assert _person_names(response.content, "contributor") == {_CONTRIBUTOR_NAME}

    def test_no_credits_without_metadata(self) -> None:
        """Credits stay off feeds that didn't ask for metadata."""
        response = self.client.get(self.feed.split("?")[0])
        assert response.status_code == _HTTP_OK
        assert not _person_names(response.content, "author")
        assert not _person_names(response.content, "contributor")
