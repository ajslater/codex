"""
Filters left out of one query: the ``omit`` set on the filter pipeline.

The choices for a filter are built with that filter left out. Leaving one
out is not the same as the grid of lists skipping it: on the grid the
Reading Lists filter still picks the lists it holds, and leaving it out of
a comic query must never put those list pks on the comics.
"""

from collections.abc import Collection
from types import MappingProxyType
from typing import Final, override

from django.test import RequestFactory
from rest_framework.request import Request

from codex.librarian.scribe.readinglists.live import add_item
from codex.models import Comic, ReadingList
from codex.views.browser.choices import BrowserChoicesView
from codex.views.browser.filters.reading_lists import (
    READING_LIST_KIND_FILTER,
    READING_LISTS_FILTER,
)
from tests.test_reading_list_kind_views import KindFixture

_KIND: Final = frozenset({READING_LIST_KIND_FILTER})
_LISTS: Final = frozenset({READING_LISTS_FILTER})


class OmitFixture(KindFixture):
    """A choices view over the kind fixture, for the reader."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.all_comics = set(Comic.objects.values_list("pk", flat=True))  # pyright: ignore[reportUninitializedInstanceVariable]

    def view(self, filters: dict, collection="series", pks=()) -> BrowserChoicesView:
        view = BrowserChoicesView()
        request = Request(RequestFactory().get("/"))
        request.user = self.reader
        view.request = request
        view.kwargs = {"collection": collection, "pks": pks}
        view.set_params(MappingProxyType({"filters": filters, "search": ""}))
        return view

    def shown(self, view: BrowserChoicesView, omit: Collection[str] = ()) -> set[int]:
        qs = view.get_filtered_queryset(Comic, omit=omit)
        return set(qs.values_list("pk", flat=True))


class OmitTests(OmitFixture):
    """An omitted filter does not narrow; the others still do."""

    def test_nothing_omitted_applies_every_filter(self) -> None:
        """The default leaves the query as it was."""
        view = self.view({READING_LISTS_FILTER: [self.mine.pk]})
        assert self.shown(view) == {self.comics[0].pk}

    def test_an_omitted_filter_does_not_narrow(self) -> None:
        """The Reading Lists filter left out: every comic."""
        view = self.view({READING_LISTS_FILTER: [self.mine.pk]})
        assert self.shown(view, _LISTS) == self.all_comics

    def test_the_other_filters_still_narrow(self) -> None:
        """The kind left out, the list filter applies."""
        filters = {
            READING_LISTS_FILTER: [self.handmade.pk],
            READING_LIST_KIND_FILTER: ["mine"],
        }
        view = self.view(filters)
        assert self.shown(view) == set()
        assert self.shown(view, _KIND) == {self.comics[1].pk}

    def test_the_kind_omitted(self) -> None:
        """Mine left out: every comic."""
        view = self.view({READING_LIST_KIND_FILTER: ["mine"]})
        assert self.shown(view) == {self.comics[0].pk}
        assert self.shown(view, _KIND) == self.all_comics


class OmitOnTheGridTests(OmitFixture):
    """On the grid of lists, omitting is apart from the grid's skipping."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.holder = ReadingList.objects.create(name="Holder", user=self.reader)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_item(self.holder, "arcs", self.tagged.pk)

    def test_omitting_the_list_filter_puts_no_list_pks_on_comics(self) -> None:
        """The held lists' pks are lists, never comics."""
        view = self.view({READING_LISTS_FILTER: [self.holder.pk]}, "arcs", (0,))
        assert self.shown(view, _LISTS) == self.all_comics

    def test_the_grid_still_shows_the_held_lists(self) -> None:
        """With the kind omitted, the list filter picks the held lists."""
        filters = {
            READING_LISTS_FILTER: [self.holder.pk],
            READING_LIST_KIND_FILTER: ["mine"],
        }
        view = self.view(filters, "arcs", (0,))
        lists = view.get_filtered_queryset(ReadingList)
        assert not lists.exists()
        lists = view.get_filtered_queryset(ReadingList, omit=_KIND)
        assert set(lists.values_list("pk", flat=True)) == {self.tagged.pk}

    def test_omitting_the_list_filter_on_the_grid(self) -> None:
        """Left out, every list shows."""
        view = self.view({READING_LISTS_FILTER: [self.holder.pk]}, "arcs", (0,))
        lists = view.get_filtered_queryset(ReadingList, omit=_LISTS)
        assert self.tagged.pk in set(lists.values_list("pk", flat=True))
        assert lists.count() > 1
