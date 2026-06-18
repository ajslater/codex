"""
Regression tests for the ``library.changed`` browser refresh gate.

The frontend reloads the current browse page only when the scoped
``/api/v4/mtime`` probe reports a value different from the ``mtime`` the
browse page last returned. Two defects broke that gate after a tag
re-import:

1. The browse page computed ``mtime`` over ``self.model`` (the *child*
   collection shown in the page) filtered by ``pk__in=route_pks`` (the
   *parent* pks). Child pk never equals a parent pk, so the aggregate was
   empty and ``page.mtime`` collapsed to EPOCH (0) — never comparable to
   the probe, which reads the route/parent collection's own ``updated_at``.

2. ``TimestampUpdater`` filtered child comics with ``updated_at > start_time``.
   SQLite stores ``updated_at`` at millisecond precision (three fractional
   digits) while ``start_time`` is a six-digit Python microsecond datetime;
   compared as TEXT a same-second comic sorts *before* ``start_time`` and was
   excluded, so the collection's ``updated_at`` never advanced and the probe
   reported no change.
"""
# Instance attributes are set in TestCase.setUp, not __init__ (the test idiom).
# pyright: reportUninitializedInstanceVariable=false

import json
import shutil
import threading
from datetime import timedelta
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.functions import Now
from django.test import Client, TestCase
from django.utils import timezone
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
TMP_DIR = Path("/tmp/codex.tests.mtime_gate")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class MtimeGateTestCase(TestCase):
    """The page mtime and the scoped probe must agree and track changes."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))
        # Filler publishers so the target publisher's pk can't coincide with
        # one of its own series' pks (the coincidence that masked defect #1).
        for i in range(5):
            Publisher.objects.create(name=f"Filler {i}")
        publisher = Publisher.objects.create(name="ZZ Press")
        imprint = Imprint.objects.create(name="ZZ Imprint", publisher=publisher)
        series = Series.objects.create(
            name="Alpha", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2020", series=series, imprint=imprint, publisher=publisher
        )
        self.publisher = publisher
        self.series = series
        self.volume = volume
        path = TMP_DIR / "a1.cbz"
        path.touch()
        self.comic = Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=1,
            name="a1",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=101,
            year=2020,
            page_count=11,
        )
        user = User.objects.create_user(username="mtime_test", password=_TEST_PASSWORD)
        self.client = Client()
        self.client.force_login(user)
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"viewMode": "cover", "orderBy": "sort_name"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _run_updater(self, start_time) -> None:
        TimestampUpdater(
            logger, LIBRARIAN_QUEUE, threading.Lock()
        ).update_library_collections(self.library, start_time, {})

    def _page_mtime(self, collection, pks) -> int:
        cache.clear()
        response = self.client.get(f"/api/v4/browse/{collection}/{pks}?page=1")
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["mtime"]

    def _probe_mtime(self, collection, pks) -> int:
        cache.clear()
        collections = json.dumps([{"collection": collection, "pks": str(pks)}])
        response = self.client.get("/api/v4/mtime", {"collections": collections})
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["maxMtime"]

    def _head(self, collection, pks) -> dict:
        cache.clear()
        response = self.client.get(f"/api/v4/browse/{collection}/{pks}/head")
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_head_matches_page_and_tracks_membership(self) -> None:
        """The head probe equals the page's (mtime, count) and tracks membership."""
        head = self._head("publishers", self.publisher.pk)
        page = self._page("publishers", self.publisher.pk)
        # Parity: the gate compares these, so they must match the page exactly.
        assert head["mtime"] == page["mtime"], (head, page)
        assert head["count"] == page["count"], (head, page)
        assert head["count"] == 1, head  # one series (Alpha) with a comic

        # A new series with a comic grows the filtered membership -> count moves,
        # which is what lets the gate detect membership changes mtime can miss.
        imprint = Imprint.objects.get(publisher=self.publisher)
        beta = Series.objects.create(
            name="Beta", imprint=imprint, publisher=self.publisher
        )
        bvol = Volume.objects.create(
            name="2021", series=beta, imprint=imprint, publisher=self.publisher
        )
        bpath = TMP_DIR / "b1.cbz"
        bpath.touch()
        beta_comic = Comic.objects.create(
            library=self.library,
            path=bpath,
            issue_number=1,
            name="b1",
            publisher=self.publisher,
            imprint=imprint,
            series=beta,
            volume=bvol,
            size=1,
            page_count=1,
        )
        grown = self._head("publishers", self.publisher.pk)["count"]
        assert grown == head["count"] + 1  # Alpha + Beta

        # Emptying Beta drops it from the view -> count falls back.
        beta_comic.delete()
        assert self._head("publishers", self.publisher.pk)["count"] == head["count"]

    def _page(self, collection, pks) -> dict:
        cache.clear()
        response = self.client.get(f"/api/v4/browse/{collection}/{pks}?page=1")
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_root_probe_reports_global_max_not_first_row(self) -> None:
        """
        The root probe must report the GLOBAL max over all collections.

        At root (many publishers) the probe aggregated per-row then took
        ``.first()``, returning whichever publisher sorts first rather than the
        newest — so a change to any other publisher was invisible to the gate.
        """
        # An alphabetically-FIRST publisher (sorts before "ZZ Press") with a
        # comic so it survives the empty-collection inner join.
        early = Publisher.objects.create(name="AAA First")
        imp = Imprint.objects.create(name="AAA Imp", publisher=early)
        ser = Series.objects.create(name="AAA Ser", imprint=imp, publisher=early)
        vol = Volume.objects.create(name="1", series=ser, imprint=imp, publisher=early)
        path = TMP_DIR / "aaa.cbz"
        path.touch()
        Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=1,
            name="aaa",
            publisher=early,
            imprint=imp,
            series=ser,
            volume=vol,
            size=1,
            page_count=1,
        )
        # ZZ Press has the LOWEST pk among comic-bearing publishers, so an
        # ``ORDER BY pk`` ``.first()`` returns it. Make it the OLD one and the
        # higher-pk publisher the NEWEST: the global max must still win.
        old = timezone.now() - timedelta(days=3)
        new = timezone.now()
        Publisher.objects.filter(pk=self.publisher.pk).update(updated_at=old)
        Publisher.objects.filter(pk=early.pk).update(updated_at=new)

        probe = self._probe_mtime("publishers", 0)  # pks 0 -> root, all publishers
        new_ms = int(new.timestamp() * 1000)
        old_ms = int(old.timestamp() * 1000)
        assert abs(probe - new_ms) <= 1, (probe, new_ms, old_ms)

    def test_page_mtime_matches_scoped_probe(self) -> None:
        """``page.mtime`` equals the ``/api/v4/mtime`` probe for the route."""
        self._run_updater(timezone.now() - timedelta(seconds=10))

        page_mtime = self._page_mtime("publishers", self.publisher.pk)
        probe_mtime = self._probe_mtime("publishers", self.publisher.pk)

        # Defect #1: page.mtime used to be 0 (empty child-by-parent-pk filter).
        assert page_mtime > 0, page_mtime
        # The gate compares these two; they must be the same scope/value.
        assert page_mtime == probe_mtime, (page_mtime, probe_mtime)

    def test_gate_fires_after_collection_bump(self) -> None:
        """A descendant change moves the probe away from the stored page mtime."""
        self._run_updater(timezone.now() - timedelta(seconds=10))
        stored_page_mtime = self._page_mtime("publishers", self.publisher.pk)

        # Re-import bumps the comic, then TimestampUpdater re-stamps the subtree.
        start_time = timezone.now()
        Comic.objects.filter(pk=self.comic.pk).update(updated_at=Now())
        self._run_updater(start_time)

        probe_mtime = self._probe_mtime("publishers", self.publisher.pk)
        # Gate condition: probe != stored page mtime -> the frontend reloads.
        assert probe_mtime != stored_page_mtime, (probe_mtime, stored_page_mtime)
        assert probe_mtime > stored_page_mtime, (probe_mtime, stored_page_mtime)

    def test_timestamp_updater_bumps_same_instant_reimport(self) -> None:
        """
        Same-second re-import still re-stamps collections (defect #2).

        A comic restamped in the same second as ``start_time`` must still
        re-stamp its collections (the fast tag-write re-import case).
        """
        baseline = Volume.objects.get(pk=self.volume.pk).updated_at

        # No delay: comic.updated_at lands in the same second as start_time,
        # the worst case for the millisecond-vs-microsecond TEXT comparison.
        start_time = timezone.now()
        Comic.objects.filter(pk=self.comic.pk).update(updated_at=Now())
        self._run_updater(start_time)

        for model, pk in (
            (Volume, self.volume.pk),
            (Series, self.series.pk),
            (Publisher, self.publisher.pk),
        ):
            bumped = model.objects.get(pk=pk).updated_at
            assert bumped > baseline, (model.__name__, bumped, baseline)

    def test_timestamp_updater_excludes_earlier_changes(self) -> None:
        """The floor-to-second bound must not match comics from prior seconds."""
        # Stamp the comic well in the past, then start an "import" now.
        old = timezone.now() - timedelta(hours=1)
        Comic.objects.filter(pk=self.comic.pk).update(updated_at=old)
        self._run_updater(timezone.now() - timedelta(seconds=5))
        baseline = Volume.objects.get(pk=self.volume.pk).updated_at

        # A fresh import whose window starts after the comic's stale mtime must
        # not re-stamp the volume (nothing changed in this import).
        self._run_updater(timezone.now())
        after = Volume.objects.get(pk=self.volume.pk).updated_at
        assert after == baseline, (after, baseline)
