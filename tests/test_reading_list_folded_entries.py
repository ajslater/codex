"""
A hand-added comic a source also holds stays the list's own.

A6 folds a hand-added entry into the source row that now holds its comic,
so a list written into its files reads back once. The folded entry was
deleted: the comic then lived only as that source's row, and removing the
source, or the comic's arc tag, took it out of the list. A folded row is
hand-added still, and keeps what a person did to it.
"""

import json
from typing import Final, override

from comicbox.readinglists import loads
from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.combine import recombine
from codex.librarian.scribe.readinglists.documents import to_json
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    import_document,
    remove_source,
)
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.librarian.scribe.readinglists.write import arc_write, mark_written
from codex.models import Comic, ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.readinglists.entries import add_comics, remove_comics
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_BAD_REQUEST: Final = 400
_LISTS: Final = "/api/v4/reading-lists"


def _cbl(name: str, *numbers: int) -> dict:
    """Return a ComicRack list of Civil War issues, stored as codex stores one."""
    books = "".join(
        f'<Book Series="Civil War" Number="{number}" Volume="2006" Year="2006" />'
        for number in numbers
    )
    text = (
        f'<?xml version="1.0"?><ReadingList><Name>{name}</Name>'
        f"<Books>{books}</Books><Matchers /></ReadingList>"
    )
    return to_json(loads(text).reading_list)


def _upload(ref: str) -> SourceSpec:
    return SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref=ref)


def _shown(reading_list: ReadingList) -> list[int | None]:
    """Return the comics the list shows, in list order."""
    return list(
        ReadingListEntry.objects.filter(reading_list=reading_list, ignored=False)
        .order_by("position", "pk")
        .values_list("comic_id", flat=True)
    )


def _entries_of(reading_list: ReadingList, comic: Comic):
    return ReadingListEntry.objects.filter(reading_list=reading_list, comic=comic)


class FoldedSourceTests(ReadingListFixture):
    """A hand-added #3, then a second source that lists #3 and #4."""

    @override
    def setUp(self) -> None:
        super().setUp()
        _, _, c3, _ = self.comics
        self.reading_list = import_document(_cbl("A", 1, 2), _upload("a.cbl"))  # pyright: ignore[reportUninitializedInstanceVariable]
        add_comics(self.reading_list, [c3.pk])
        import_document(_cbl("B", 3, 4), _upload("b.cbl"), into=self.reading_list)
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _folded(self) -> ReadingListEntry:
        return _entries_of(self.reading_list, self.comics[2]).get()

    def test_the_source_holds_it_once(self) -> None:
        """Both the hand and the second source hold #3: it shows once."""
        c1, c2, c3, c4 = self.comics
        assert _shown(self.reading_list) == [c1.pk, c2.pk, c3.pk, c4.pk]

    def test_removing_the_source_keeps_it(self) -> None:
        """The comic was added by hand, so it outlives the source."""
        c1, c2, c3, _ = self.comics
        source = ReadingListSource.objects.get(
            reading_list=self.reading_list, ref="b.cbl"
        )
        assert remove_source(source)
        assert _shown(self.reading_list) == [c1.pk, c2.pk, c3.pk]
        assert self._folded().manual

    def test_removing_it_hides_it(self) -> None:
        """The source would bring a deleted entry back, so it is hidden."""
        c1, c2, c3, c4 = self.comics
        result = remove_comics(self.reading_list, [c3.pk])
        assert (result["removed"], result["hidden"]) == (0, 1)
        recombine(self.reading_list)
        assert _shown(self.reading_list) == [c1.pk, c2.pk, c4.pk]
        assert self._folded().ignored

    def test_deleting_its_entry_hides_it(self) -> None:
        """Removing the one entry, as Edit Issues does, hides it too."""
        c1, c2, _, c4 = self.comics
        url = f"{_LISTS}/{self.reading_list.pk}/entries/{self._folded().pk}"
        response = self.client.delete(url)
        assert response.status_code == _OK, response.content
        assert response.json()["data"]["deleted"] is False
        recombine(self.reading_list)
        assert _shown(self.reading_list) == [c1.pk, c2.pk, c4.pk]

    def test_hiding_it_lasts(self) -> None:
        """A hidden folded entry stays hidden when the list is recomputed."""
        c1, c2, _, c4 = self.comics
        ReadingListEntry.objects.filter(pk=self._folded().pk).update(ignored=True)
        recombine(self.reading_list)
        assert _shown(self.reading_list) == [c1.pk, c2.pk, c4.pk]
        assert self._folded().ignored

    def test_a_hand_reorder_keeps_its_place(self) -> None:
        """A locked order keeps a folded entry where a person put it."""
        c1, c2, c3, c4 = self.comics
        for position, comic in enumerate((c3, c1, c2, c4)):
            _entries_of(self.reading_list, comic).update(position=position)
        self.reading_list.order_locked = True
        self.reading_list.save()
        recombine(self.reading_list)
        assert _shown(self.reading_list) == [c3.pk, c1.pk, c2.pk, c4.pk]

    def test_picking_another_comic_for_it_lasts(self) -> None:
        """A pick on a folded entry replaces its comic; #3 does not come back."""
        c1, c2, c3, c4 = self.comics
        url = f"{_LISTS}/{self.reading_list.pk}/entries/{self._folded().pk}"
        response = self.client.patch(
            url, data=json.dumps({"comic": c4.pk}), content_type="application/json"
        )
        assert response.status_code == _OK, response.content
        recombine(self.reading_list)
        shown = _shown(self.reading_list)
        assert shown == [c1.pk, c2.pk, c4.pk, c4.pk]
        assert c3.pk not in shown


class FoldedTagsTests(ReadingListFixture):
    """A hand-made list written into its comics' files, then read back."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.reading_list = ReadingList.objects.create(name="Hand Made")  # pyright: ignore[reportUninitializedInstanceVariable]
        for position, comic in enumerate(self.comics[:3]):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
        arc = arc_write(self.reading_list)
        mark_written(self.reading_list, arc.name)
        for pk, patch_ in arc.patches.items():
            number = patch_["arcs"][arc.name].get("number")
            self.tag(Comic.objects.get(pk=pk), arc.name, number)
        sync_tag_lists()
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def test_a_tagged_entry_keeps_its_comic(self) -> None:
        """
        A pick or a "not in library" on a tagged entry is refused.

        The arc tag says which comic it is, so a recompute would put the
        tagged comic back; the entry stays hand-added either way.
        """
        c1, c2, c3, c4 = self.comics
        for comic in (c4.pk, None):
            with self.subTest(comic=comic):
                entry = _entries_of(self.reading_list, c2).get()
                url = f"{_LISTS}/{self.reading_list.pk}/entries/{entry.pk}"
                response = self.client.patch(
                    url,
                    data=json.dumps({"comic": comic}),
                    content_type="application/json",
                )
                recombine(self.reading_list)
                entry = _entries_of(self.reading_list, c2).get()
                assert entry.manual
                assert entry.comic_id == c2.pk
                assert _shown(self.reading_list) == [c1.pk, c2.pk, c3.pk]
                assert response.status_code == _BAD_REQUEST, response.content
                assert "arc" in str(response.json()), response.content

    def test_it_reads_back_once(self) -> None:
        """The arc joins the list it was written from, comic for comic."""
        assert _shown(self.reading_list) == [comic.pk for comic in self.comics[:3]]

    def test_untagging_one_comic_keeps_it(self) -> None:
        """A comic whose arc tag goes stays: it was added by hand."""
        self.untag(self.comics[1])
        sync_tag_lists()
        assert _shown(self.reading_list) == [comic.pk for comic in self.comics[:3]]

    def test_untagging_every_comic_keeps_the_list(self) -> None:
        """The arc going leaves the list a person made, whole."""
        for comic in self.comics[:3]:
            self.untag(comic)
        sync_tag_lists()
        assert ReadingList.objects.filter(pk=self.reading_list.pk).exists()
        assert _shown(self.reading_list) == [comic.pk for comic in self.comics[:3]]


class ReAddHiddenTests(ReadingListFixture):
    """A person hides a source's #2, then adds #2 by hand."""

    def test_the_shown_again_row_is_hand_added(self) -> None:
        """It was added by hand, so it stays when the source goes."""
        _, c2, _, _ = self.comics
        owner = User.objects.create_user(username="owner", password=_PW)
        reading_list = import_document(_cbl("A", 1, 2), _upload("a.cbl"), user=owner)
        remove_comics(reading_list, [c2.pk])
        assert add_comics(reading_list, [c2.pk]) == 1
        assert remove_source(ReadingListSource.objects.get(reading_list=reading_list))
        assert _shown(reading_list) == [c2.pk]
