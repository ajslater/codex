"""
KOReader document hashes beside Comic, and the job that backfills them.

What these tests pin:

* A comic's hashes are computed from its file; the binary hash only when
  asked, and a file that can't be read leaves it null.
* The backfill hashes comics with no binary hash, with a row or without,
  one batch per task, re-queued; an unreadable file still gets its name
  hash; an earlier abort does not stop the next run; it does nothing with
  KOReader Sync off; turning the flag on queues it.
"""

import json
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import Final
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.librarian.scribe.janitor.tasks import JanitorKoreaderHashTask
from codex.librarian.scribe.koreader_hash import (
    koreader_name_md5,
    koreader_partial_md5,
)
from codex.models import Comic, ComicKoreaderHash
from tests.koreader_fixtures import (
    KOSyncTestCase,
    binary_hash,
    name_hash,
    set_flag,
)

_HTTP_OK: Final = 200


class KOSyncHashTestCase(KOSyncTestCase):
    """A comic's hashes, computed from its file."""

    def test_compute_sets_both_hashes(self) -> None:
        """The binary and the filename hash match the file."""
        assert binary_hash(self.comic) == koreader_partial_md5(self.comic.path)
        assert name_hash(self.comic) == koreader_name_md5(self.comic.path)

    def test_unreadable_file_leaves_the_binary_hash_null(self) -> None:
        """A file that can't be read doesn't fail the hashing."""
        # A directory: stat works, open fails.
        hashes = ComicKoreaderHash.compute(
            self.comic.pk, self.library.path, binary=True
        )
        assert hashes.binary_hash is None
        assert hashes.name_hash == koreader_name_md5(self.library.path)

    def test_without_binary_the_file_is_not_read(self) -> None:
        with patch(
            "codex.models.koreader.koreader_partial_md5",
            side_effect=AssertionError("read the file"),
        ):
            hashes = ComicKoreaderHash.compute(
                self.comic.pk, self.comic.path, binary=False
            )
        assert hashes.binary_hash is None
        assert hashes.name_hash == koreader_name_md5(self.comic.path)


class KOSyncBackfillTestCase(KOSyncTestCase):
    """The janitor job hashes comics imported before the flag existed."""

    def _janitor(self) -> Janitor:
        return Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())

    @staticmethod
    def _clear_hashes() -> None:
        """No hash rows: every comic's state after the 0060 upgrade."""
        ComicKoreaderHash.objects.all().delete()

    @staticmethod
    def _unhashed():
        """Comics with no binary hash, whether or not they have a row."""
        hashed = ComicKoreaderHash.objects.filter(binary_hash__isnull=False)
        return Comic.objects.exclude(pk__in=hashed.values("comic_id"))

    def _assert_hashed(self, comic: Comic) -> None:
        assert binary_hash(comic) == koreader_partial_md5(comic.path)
        assert name_hash(comic) == koreader_name_md5(comic.path)

    def test_backfill_hashes_comics_without_hashes(self) -> None:
        """Every comic with a readable file gets both hashes."""
        self._clear_hashes()
        self._janitor().koreader_hash_backfill()
        for comic in Comic.objects.all():
            self._assert_hashed(comic)

    def test_backfill_fills_a_null_binary_hash(self) -> None:
        """A comic imported with the flag off has only its name hash."""
        ComicKoreaderHash.objects.update(binary_hash=None)
        self._janitor().koreader_hash_backfill()
        for comic in Comic.objects.all():
            self._assert_hashed(comic)

    def test_backfill_skips_unreadable_files(self) -> None:
        """A missing file stays null and doesn't stall the run."""
        self._clear_hashes()
        Path(self.comic.path).unlink()
        self._janitor().koreader_hash_backfill()
        assert binary_hash(self.comic) is None
        assert binary_hash(self.private_comic)

    def test_an_earlier_abort_does_not_stop_the_next_run(self) -> None:
        """
        The abort event is shared with every scribe job.

        Left set by an earlier abort, the next run exited at once with
        "Hashed 0 comics".
        """
        self._clear_hashes()
        event = Event()
        event.set()
        Janitor(logger, LIBRARIAN_QUEUE, Lock(), event).koreader_hash_backfill()
        assert not self._unhashed().exists()
        assert not event.is_set()

    def test_one_batch_per_task_requeued_while_rows_remain(self) -> None:
        """
        A batch per task lets queued imports and tag writes go between.

        The scribe runs one task at a time, so a backfill of a large
        library held it until done.
        """
        self._clear_hashes()
        queue = MagicMock()
        janitor = Janitor(logger, queue, Lock(), Event())
        first_pk = Comic.objects.order_by("pk").values_list("pk", flat=True)[0]
        with patch("codex.librarian.scribe.janitor.koreader._BATCH_SIZE", 1):
            janitor.handle_task(JanitorKoreaderHashTask())
            assert self._unhashed().count() == 1
            requeued = [
                call.args[0]
                for call in queue.put.call_args_list
                if isinstance(call.args[0], JanitorKoreaderHashTask)
            ]
            assert len(requeued) == 1
            assert requeued[0].last_pk == first_pk
            janitor.handle_task(requeued[0])
        assert not self._unhashed().exists()

    def test_an_unreadable_file_still_gets_its_name_hash(self) -> None:
        """The name hash needs no file; Filename matching can use it."""
        self._clear_hashes()
        Path(self.comic.path).unlink()
        self._janitor().koreader_hash_backfill()
        assert binary_hash(self.comic) is None
        assert name_hash(self.comic) == koreader_name_md5(self.comic.path)

    def test_backfill_does_nothing_with_the_flag_off(self) -> None:
        """The nightly run is a no-op while sync is off."""
        set_flag(on=False)
        cache.clear()
        self._clear_hashes()
        self._janitor().koreader_hash_backfill()
        assert not ComicKoreaderHash.objects.exists()

    def test_turning_the_flag_on_queues_the_backfill(self) -> None:
        """The admin flag hook queues the job."""
        set_flag(on=False)
        admin = User.objects.create_superuser(
            username="admin",
            email="",
            password="x",  # noqa: S106
        )
        self.client.force_login(admin)
        with patch("codex.views.admin.flag.LIBRARIAN_QUEUE") as queue:
            key = AdminFlagChoices.KOREADER_SYNC.value
            body = {"data": {"type": "flags", "id": key, "attributes": {"on": True}}}
            response = self.client.patch(
                f"/api/v4/admin/flags/{key}",
                data=json.dumps(body),
                content_type="application/json",
            )
        assert response.status_code == _HTTP_OK, response.content
        queued = [call.args[0] for call in queue.put.call_args_list]
        assert any(isinstance(task, JanitorKoreaderHashTask) for task in queued)
