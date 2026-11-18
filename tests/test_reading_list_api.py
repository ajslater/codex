"""
The reading list API: admin import and review, owner edits, export.

Uploads go through the real preview, the import job runs inline, and the
entry edits are checked against what a recombine keeps.
"""

import json
from multiprocessing import Queue
from threading import Lock
from typing import Final, override
from unittest.mock import patch

from comicbox.readinglists import dumps, loads
from django.contrib.auth.models import User
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from loguru import logger

from codex.librarian.scribe.readinglists.documents import UNSUPPORTED_FORMAT
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.librarian.scribe.readinglists.tasks import ReadingListImportTask
from codex.librarian.scribe.readinglists.worker import ReadingListWorker
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_list_combine import _CBL
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_CREATED: Final = 201
_BAD_REQUEST: Final = 400
_ACCEPTED: Final = 202
_FORBIDDEN: Final = 403
_NOT_FOUND: Final = 404
_ADMIN: Final = "/api/v4/admin/reading-lists"
_LISTS: Final = "/api/v4/reading-lists"
_IMPORT_QUEUE: Final = "codex.views.admin.reading_lists.imports.LIBRARIAN_QUEUE"


def _data(response):
    body = response.json()
    return body.get("data", body) if isinstance(body, dict) else body


class ReadingListApiTests(ReadingListFixture):
    """Import a CBL, review it, export it."""

    @override
    def setUp(self) -> None:
        super().setUp()
        caches["tagging"].clear()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.admin)

    def _import_cbl(self) -> ReadingList:
        """Upload, preview and import the CBL, running the job inline."""
        upload = SimpleUploadedFile("civil-war.cbl", _CBL.encode(), "application/xml")
        response = self.client.post(f"{_ADMIN}/preview", {"files": [upload]})
        assert response.status_code == _OK, response.content
        cards = _data(response)["cards"]
        assert len(cards) == 1
        card = cards[0]
        assert (card["count"], card["matched"]) == (4, 3)
        with patch(_IMPORT_QUEUE) as queue:
            response = self.client.post(
                f"{_ADMIN}/import",
                data=json.dumps({"items": [{"token": card["token"]}]}),
                content_type="application/json",
            )
        assert response.status_code == _ACCEPTED, response.content
        task = queue.put.call_args.args[0]
        assert isinstance(task, ReadingListImportTask)
        ReadingListWorker(logger, Queue(), Lock()).handle_task(task)
        return ReadingList.objects.get(name="[Marvel] Civil War (CBRO)")

    def test_preview_writes_nothing(self) -> None:
        """A preview saves no list."""
        upload = SimpleUploadedFile("civil-war.cbl", _CBL.encode())
        response = self.client.post(f"{_ADMIN}/preview", {"files": [upload]})
        assert response.status_code == _OK, response.content
        assert not ReadingList.objects.exists()

    def test_bad_file_gets_an_error_card(self) -> None:
        """A file that is not a list explains itself and stops nothing."""
        good = SimpleUploadedFile("good.cbl", _CBL.encode())
        bad = SimpleUploadedFile("bad.cbl", b"not a list")
        response = self.client.post(f"{_ADMIN}/preview", {"files": [bad, good]})
        cards = _data(response)["cards"]
        assert "error" in cards[0]
        assert cards[1]["count"] == 4  # noqa: PLR2004

    def test_comicbox_formats_are_not_read(self) -> None:
        """Only ComicRack lists import: comicbox's YAML and JSON are refused."""
        model = loads(_CBL).reading_list
        uploads = [
            SimpleUploadedFile(f"civil-war.{fmt}", dumps(model, fmt).encode())
            for fmt in ("yaml", "json")
        ]
        json_cbl = SimpleUploadedFile(
            "civil-war.json", dumps(model, "json-cbl").encode()
        )
        response = self.client.post(
            f"{_ADMIN}/preview", {"files": [*uploads, json_cbl]}
        )
        cards = _data(response)["cards"]
        assert [card.get("error") for card in cards[:2]] == [UNSUPPORTED_FORMAT] * 2
        assert cards[2]["count"] == 4  # noqa: PLR2004

    def test_import_and_table(self) -> None:
        """The imported list shows in the table with its coverage."""
        reading_list = self._import_cbl()
        response = self.client.get(_ADMIN)
        assert response.status_code == _OK
        rows = _data(response)["lists"]
        row = next(row for row in rows if row["pk"] == reading_list.pk)
        assert (row["total"], row["matched"], row["owner"]) == (4, 3, None)
        assert [source["kind"] for source in row["sources"]] == ["upload"]

    def test_review_edits(self) -> None:
        """Pick, hide, reorder and accept, as the review screen does."""
        reading_list = self._import_cbl()
        url = f"{_LISTS}/{reading_list.pk}/entries"
        entries = _data(self.client.get(url, {"filter": "missing"}))["entries"]
        assert [entry["seriesName"] for entry in entries] == ["The Amazing Spider-Man"]
        missing = entries[0]["pk"]

        candidates = _data(
            self.client.get(f"{url}/{missing}/candidates", {"q": "civil"})
        )["candidates"]
        assert {candidate["pk"] for candidate in candidates} == {
            comic.pk for comic in self.comics
        }
        response = self.client.patch(
            f"{url}/{missing}",
            data=json.dumps({"comic": self.comics[3].pk}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        assert _data(response)["matchTier"] == ReadingListMatchTier.MANUAL

        last = _data(self.client.get(url))["entries"][-1]["pk"]
        self.client.patch(
            f"{url}/{last}",
            data=json.dumps({"ignored": True}),
            content_type="application/json",
        )
        response = self.client.post(
            f"{url}/reorder",
            data=json.dumps({"entry": missing, "position": 0}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        reading_list.refresh_from_db()
        assert reading_list.order_locked
        first = ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
            "position"
        )[0]
        assert first.pk == missing

    def test_export_carries_matched_ids_and_uuid(self) -> None:
        """Export writes the list; json-cbl keeps the list's UUID."""
        reading_list = self._import_cbl()
        response = self.client.get(
            f"{_LISTS}/{reading_list.pk}/export", {"fmt": "json-cbl"}
        )
        assert response.status_code == _OK, response.content
        assert str(reading_list.uuid) in response.content.decode()
        cbl = self.client.get(f"{_LISTS}/{reading_list.pk}/export", {"fmt": "cbl"})
        assert cbl.status_code == _OK
        parsed = loads(cbl.content).reading_list
        assert len(parsed["entries"]) == 4  # noqa: PLR2004

    def test_export_offers_only_comicrack_formats(self) -> None:
        """Comicbox's own YAML and JSON list formats are not exported."""
        reading_list = self._import_cbl()
        for fmt in ("yaml", "json"):
            response = self.client.get(
                f"{_LISTS}/{reading_list.pk}/export", {"fmt": fmt}
            )
            assert response.status_code == _BAD_REQUEST, fmt

    def test_non_admin_cannot_edit_a_global_list(self) -> None:
        """A user sees a global list's comics but cannot change its entries."""
        reading_list = self._import_cbl()
        self.client.force_login(self.user)
        response = self.client.get(f"{_LISTS}/{reading_list.pk}/entries")
        assert response.status_code == _FORBIDDEN
        response = self.client.get(_ADMIN)
        assert response.status_code == _FORBIDDEN

    def _personal_list(self) -> int:
        """Make a personal list holding #2, then put #1 before it."""
        self.client.force_login(self.user)
        response = self.client.post(
            f"{_LISTS}/",
            data=json.dumps({"name": "Mine", "comics": [self.comics[1].pk]}),
            content_type="application/json",
        )
        assert response.status_code == _CREATED, response.content
        pk = _data(response)["pk"]
        response = self.client.post(
            f"{_LISTS}/{pk}/entries",
            data=json.dumps({"comics": [self.comics[0].pk], "position": 0}),
            content_type="application/json",
        )
        assert _data(response)["added"] == 1
        return pk

    def test_personal_list_order_and_rename(self) -> None:
        """Comics go where they are put; a rename sticks."""
        pk = self._personal_list()
        order = list(
            ReadingListEntry.objects.filter(reading_list_id=pk)
            .order_by("position")
            .values_list("comic_id", flat=True)
        )
        assert order == [self.comics[0].pk, self.comics[1].pk]
        response = self.client.patch(
            f"{_LISTS}/{pk}",
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        assert _data(response)["name"] == "Renamed"

    def test_personal_list_duplicate(self) -> None:
        """A duplicate copies every entry into another list of one's own."""
        pk = self._personal_list()
        response = self.client.post(
            f"{_LISTS}/{pk}/duplicate", data="{}", content_type="application/json"
        )
        assert response.status_code == _CREATED
        copy_pk = _data(response)["pk"]
        assert ReadingListEntry.objects.filter(reading_list_id=copy_pk).count() == 2  # noqa: PLR2004
        menu = _data(self.client.get(f"{_LISTS}/"))["lists"]
        assert {item["name"] for item in menu} == {"Mine", "Mine (copy)"}

    def test_admin_copies_a_users_list_to_global(self) -> None:
        """A global copy in the same order; the user's list stays theirs."""
        pk = self._personal_list()
        self.client.force_login(self.admin)
        response = self.client.post(f"{_ADMIN}/{pk}/copy_global")
        assert response.status_code == _OK, response.content
        assert _data(response) == {"copied": 1}
        original = ReadingList.objects.get(pk=pk)
        assert original.user == self.user
        copy = ReadingList.objects.get(user__isnull=True, name="Mine")
        assert copy.order_locked
        order = list(
            ReadingListEntry.objects.filter(reading_list=copy)
            .order_by("position")
            .values_list("comic_id", "manual")
        )
        assert order == [(self.comics[0].pk, True), (self.comics[1].pk, True)]
        # Global lists are skipped, so a second pass over the copy adds none.
        response = self.client.post(f"{_ADMIN}/{copy.pk}/copy_global")
        assert _data(response) == {"copied": 0}

    def test_only_admins_copy_to_global(self) -> None:
        """A user cannot make their list global through the admin action."""
        pk = self._personal_list()
        response = self.client.post(f"{_ADMIN}/{pk}/copy_global")
        assert response.status_code == _FORBIDDEN
        assert not ReadingList.objects.filter(user__isnull=True).exists()

    def test_add_a_selection(self) -> None:
        """A series adds its comics in reading order, after the list's last."""
        pk = self._personal_list()
        response = self.client.post(
            f"{_LISTS}/{pk}/add",
            data=json.dumps({"targets": {"series": [self.comics[0].series_id]}}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        assert _data(response)["added"] == 4  # noqa: PLR2004
        order = list(
            ReadingListEntry.objects.filter(reading_list_id=pk)
            .order_by("position")
            .values_list("comic_id", flat=True)
        )
        assert order == [
            self.comics[0].pk,
            self.comics[1].pk,
            *(comic.pk for comic in self.comics),
        ]

    def test_personal_list_is_private(self) -> None:
        """Another user can neither see nor change it; its owner deletes it."""
        pk = self._personal_list()
        self.client.force_login(self.admin)
        response = self.client.get(f"{_LISTS}/{pk}/entries")
        assert response.status_code == _NOT_FOUND
        self.client.force_login(self.user)
        assert self.client.delete(f"{_LISTS}/{pk}").status_code == _OK
        assert not ReadingList.objects.filter(pk=pk).exists()

    def test_series_mapping_and_combine_dry_run(self) -> None:
        """A mapping is saved from a row; a dry run combines without saving."""
        reading_list = self._import_cbl()
        entry = ReadingListEntry.objects.get(
            reading_list=reading_list, comic__isnull=True
        )
        with patch("codex.views.admin.reading_lists.review.LIBRARIAN_QUEUE"):
            response = self.client.post(
                f"{_ADMIN}/series-mappings",
                data=json.dumps(
                    {
                        "list": reading_list.pk,
                        "entry": entry.pk,
                        "series": self.comics[0].series_id,
                    }
                ),
                content_type="application/json",
            )
        assert response.status_code == _CREATED, response.content
        assert _data(response)["seriesKey"] == "the amazing spider man"

        self.tag(self.comics[0], "Civil War", 1)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War")
        response = self.client.post(
            f"{_ADMIN}/combine",
            data=json.dumps(
                {"primary": reading_list.pk, "others": [tags_list.pk], "dryRun": True}
            ),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        assert _data(response)["total"] == 4  # noqa: PLR2004
        assert ReadingListSource.objects.filter(reading_list=tags_list).exists()

    def test_bulk_delete(self) -> None:
        """Selected lists are deleted together."""
        reading_list = self._import_cbl()
        response = self.client.post(
            f"{_ADMIN}/bulk",
            data=json.dumps({"action": "delete", "pks": [reading_list.pk]}),
            content_type="application/json",
        )
        assert _data(response)["deleted"] >= 1
        assert not ReadingList.objects.filter(pk=reading_list.pk).exists()

    def _grid(self, kind: str = "") -> dict[str, str]:
        params = {
            "filters": json.dumps({"readingListKind": kind}),
            "search": "",
            "show": json.dumps(
                {"publishers": True, "imprints": True, "series": True, "volumes": True}
            ),
            "view_mode": "cover",
        }
        response = self.client.get("/api/v4/browse/arcs/0", params)
        assert response.status_code == _OK, response.content
        rows = _data(response)["collections"]
        return {row["name"]: row["listSources"] for row in rows}

    def test_grid_sources_label_and_kind_filter(self) -> None:
        """The grid names each list's sources and narrows curated from tags."""
        self._import_cbl()
        self.tag(self.comics[0], "Civil War", 1)
        sync_tag_lists()
        assert self._grid() == {
            "[Marvel] Civil War (CBRO)": "Upload",
            "Civil War": "Tags",
        }
        assert set(self._grid("curated")) == {"[Marvel] Civil War (CBRO)"}
        assert set(self._grid("tags")) == {"Civil War"}
