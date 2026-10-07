"""Integration tests for the session-agnostic online-tag prompt endpoints."""

import shutil
from datetime import timedelta
from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import caches
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.tasks import (
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PROMPTS_URL: Final = "/api/v4/admin/tag-prompts"
_QUEUE_TARGET: Final = "codex.views.admin.onlinetag.LIBRARIAN_QUEUE"
_TMP_DIR: Final = tmp_dir("codex.tests.onlinetag_prompt_covers")
_LIBRARY_DIR: Final = _TMP_DIR / "library"
_COVERS_ROOT: Final = _TMP_DIR / "covers"
# Not a real WEBP; the prompt list only stats the thumb.
_COVER_BYTES: Final = b"RIFF\x00\x00\x00\x00WEBPfake-cover-bytes"
_MANY_PROMPTS: Final = 5


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _make_admin() -> User:
    return User.objects.create_user(
        username="tag_prompts_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


def _prompt(fingerprint: str, pk: int) -> dict:
    return {
        "fingerprint": fingerprint,
        "pk": pk,
        "path": f"/c/{pk}.cbz",
        "source": "metron",
        "candidates": [],
        "mode": "auto",
        "formats": ["COMIC_INFO"],
        "delete_original": False,
    }


class TagPromptsAuthTestCase(TestCase):
    """The prompt endpoints require admin auth."""

    def test_anonymous_blocked(self) -> None:
        response = Client().get(_PROMPTS_URL)
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagPromptsTestCase(TestCase):
    """List, resolve, and skip-all operate on the global pending-prompt cache."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        self.client.force_login(_make_admin())

    def test_lists_pending_prompts(self) -> None:
        set_pending_prompts({"fp1": _prompt("fp1", 1), "fp2": _prompt("fp2", 2)})

        response = self.client.get(_PROMPTS_URL)

        assert response.status_code == HTTPStatus.OK
        prompts = _v4(response)["prompts"]
        fingerprints = {p["fingerprint"] for p in prompts}
        assert fingerprints == {"fp1", "fp2"}
        # No Comic rows back these fixtures, so neither has a cover to show.
        assert [p["fileCover"] for p in prompts] == [None, None]

    def test_lists_empty_when_no_prompts(self) -> None:
        response = self.client.get(_PROMPTS_URL)

        assert response.status_code == HTTPStatus.OK
        assert _v4(response)["prompts"] == []

    def test_resolve_enqueues_task_by_fingerprint(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(
                f"{_PROMPTS_URL}/fp1",
                data={"action": "choose", "payload": "0"},
                content_type="application/json",
            )

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagPromptResponseTask)
        assert task.prompt_fingerprint == "fp1"
        assert task.action == "choose"
        assert task.payload == 0
        assert task.chosen_volume_id is None

    def test_skip_all_enqueues_task(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(f"{_PROMPTS_URL}/skip-all")

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagSkipAllPromptsTask)


class TagPromptsFileCoverTestCase(TestCase):
    """
    The prompt list carries each file's own cover, derived when served.

    The dialog shows it above the candidates so the admin can compare. It is
    computed on the GET, never stored, so the cached prompts the answer path
    reads keep their shape and prompts cached before the field existed get
    one too.
    """

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        _LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        _COVERS_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, _TMP_DIR, ignore_errors=True)
        # COVERS_ROOT is resolved from the config dir at import time, so
        # redirect the attribute rather than the setting it came from.
        patcher = patch.object(CoverPathMixin, "COVERS_ROOT", _COVERS_ROOT)
        patcher.start()
        self.addCleanup(patcher.stop)

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        library = Library.objects.create(path=str(_LIBRARY_DIR))
        self.comics = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in range(1, _MANY_PROMPTS + 1):
            # Comic.save() stats its file.
            path = _LIBRARY_DIR / f"{n}.cbz"
            path.touch()
            comic = Comic.objects.create(
                library=library,
                path=path,
                issue_number=n,
                name=str(n),
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                file_type="CBZ",
            )
            self.comics.append(comic)
        self.comic = self.comics[0]  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(_make_admin())

    def _write_cover(self, data: bytes) -> None:
        cover_path = CoverPathMixin.get_cover_path(self.comic.pk, custom=False)
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(data)

    def _mtime(self) -> int:
        updated_at = Comic.objects.get(pk=self.comic.pk).updated_at
        return int(updated_at.timestamp() * 1000)

    def _file_cover(self, prompt: dict | None = None) -> dict | None:
        prompt = prompt or _prompt("fp1", self.comic.pk)
        set_pending_prompts({prompt["fingerprint"]: prompt})
        response = self.client.get(_PROMPTS_URL)
        assert response.status_code == HTTPStatus.OK
        (served,) = _v4(response)["prompts"]
        return served["fileCover"]

    def test_pending_without_a_thumb(self) -> None:
        assert self._file_cover() == {
            "pk": self.comic.pk,
            "mtime": self._mtime(),
            "status": "pending",
        }

    def test_ready_with_a_thumb(self) -> None:
        self._write_cover(_COVER_BYTES)

        file_cover = self._file_cover()

        assert file_cover
        assert file_cover["status"] == "ready"

    def test_failed_on_the_zero_byte_marker(self) -> None:
        self._write_cover(b"")

        file_cover = self._file_cover()

        assert file_cover
        assert file_cover["status"] == "failed"

    def test_none_when_the_comic_is_gone(self) -> None:
        gone_pk = max(comic.pk for comic in self.comics) + 1000

        assert self._file_cover(_prompt("fp1", gone_pk)) is None

    def test_representative_from_comics_when_pk_is_absent(self) -> None:
        prompt = _prompt("fp1", self.comic.pk)
        del prompt["pk"]
        prompt["comics"] = [
            {"pk": self.comic.pk, "path": str(self.comic.path)},
            {"pk": self.comics[1].pk, "path": str(self.comics[1].path)},
        ]

        file_cover = self._file_cover(prompt)

        assert file_cover
        assert file_cover["pk"] == self.comic.pk

    def test_cached_prompt_is_not_widened(self) -> None:
        # The answer path reads the cache; the GET must only add to copies.
        self._file_cover()

        cached = get_pending_prompts()["fp1"]
        assert "file_cover" not in cached
        assert cached == _prompt("fp1", self.comic.pk)

    def test_one_comic_query_however_many_prompts(self) -> None:
        def comic_queries(comics: list[Comic]) -> int:
            set_pending_prompts(
                {f"fp{c.pk}": _prompt(f"fp{c.pk}", c.pk) for c in comics}
            )
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(_PROMPTS_URL)
            assert response.status_code == HTTPStatus.OK
            assert len(_v4(response)["prompts"]) == len(comics)
            return sum('FROM "codex_comic"' in q["sql"] for q in ctx.captured_queries)

        assert comic_queries(self.comics[:1]) == 1
        assert comic_queries(self.comics) == 1

    def test_mtime_follows_updated_at(self) -> None:
        before = self._file_cover()
        later = self.comic.updated_at + timedelta(seconds=5)
        Comic.objects.filter(pk=self.comic.pk).update(updated_at=later)

        after = self._file_cover()

        assert before
        assert after
        assert after["mtime"] == int(later.timestamp() * 1000)
        assert after["mtime"] != before["mtime"]
