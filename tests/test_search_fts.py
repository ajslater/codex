"""
FTS5 ``demote_joins`` regression guard.

The browser filter pipeline calls
:meth:`codex.views.browser.filters.filter.BrowserFilterView.force_inner_joins`
on every queryset that participates in search. That helper unconditionally
demotes ``codex_library`` (and ``codex_comic`` when the model isn't Comic),
and **conditionally** demotes ``codex_comicfts`` only when ``self.fts_mode``
is True.

The conditional ``codex_comicfts`` demotion exists because SQLite's FTS5
``MATCH`` operator only works when the FTS5 virtual table is INNER-joined to
the rest of the query. A LEFT OUTER JOIN raises::

    sqlite3.OperationalError: unable to use function MATCH in the requested context

Stage-5 backlog item R1 (`tasks/browser-views-perf/05-replan.md` §3, sub-plan
`03-filters.md` #5) flagged ``force_inner_joins`` as a candidate for
conditional demotion. This test locks the contract in as a hard regression
guard before any future perf work tries to skip the demote on the FTS5 table.

Why the carrier queries here look unusual:

* ``Comic.objects.values("comicfts__pk")`` puts ``codex_comicfts`` in the
  alias map as ``LEFT OUTER JOIN`` without any non-null filter through the
  join chain — so Django's optimizer leaves it alone, and the demote in
  ``force_inner_joins`` is observably load-bearing.
* The failure-mode tests use ``qs.query.promote_joins({"codex_comicfts"})``
  to flip the FTS join from INNER back to LEFT OUTER. ``promote_joins`` is
  the documented inverse of ``demote_joins`` (both live on
  :class:`django.db.models.sql.query.Query`), so it's the cleanest way to
  reconstruct the exact alias-map state the demote exists to prevent —
  no contrived OR/IS NULL clauses that themselves trip FTS5's context
  rules.

Filtering through ``comic__comicfts__match`` directly — the shape used by
the production filter pipeline — is intentionally **not** the assertion
target for the demote, because Django's optimizer auto-promotes that join
to INNER before ``force_inner_joins`` ever runs.
"""

import shutil
from pathlib import Path
from typing import override

import pytest
from django.db import OperationalError, connection
from django.test import TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.views.browser.filters.filter import BrowserFilterView

TMP_DIR = Path("/tmp/codex.tests.fts")  # noqa: S108


class _FTSCallableView:
    """
    Minimal stand-in exposing only the attribute ``force_inner_joins`` reads.

    ``BrowserFilterView.force_inner_joins`` is an unbound method on the
    view class but only ever touches ``self.fts_mode`` and the queryset's
    own ``model`` / ``demote_joins`` helpers. Instantiating the full DRF
    view stack just to flip a single boolean would obscure what the test
    is actually asserting.
    """

    force_inner_joins = BrowserFilterView.force_inner_joins

    def __init__(self, *, fts_mode: bool) -> None:
        self.fts_mode = fts_mode


class FTSForceInnerJoinsTestCase(TestCase):
    """Regression guard for the FTS5 demote-joins contract."""

    @override
    def setUp(self) -> None:
        """Seed two comics + two FTS rows with distinguishable tokens."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
        )

        def _make_comic(slug: str, issue: int) -> Comic:
            path = TMP_DIR / f"{slug}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=issue,
                name=slug,
                publisher=publisher,
                imprint=imprint,
                series=self.series,
                volume=volume,
                size=1,
            )

        self.comic_wonder = _make_comic("wonder", 1)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic_phoenix = _make_comic("phoenix", 2)  # pyright: ignore[reportUninitializedInstanceVariable]

        # ``ComicFTS`` is ``managed=False`` and its column list is
        # rewritten by SQL-level migrations (most recently 0039), so the
        # Django field set drifts from the live schema. Insert via raw
        # SQL using only the columns that have been stable since 0029
        # (``comic_id`` + ``name``) — FTS5 fills the unspecified columns
        # with empty strings.
        with connection.cursor() as cur:
            cur.execute(
                "INSERT INTO codex_comicfts (comic_id, name) VALUES (?, ?), (?, ?)",
                [
                    self.comic_wonder.pk,
                    "wonder",
                    self.comic_phoenix.pk,
                    "phoenix",
                ],
            )

    @override
    def tearDown(self) -> None:
        """Clear the FTS table and the temp comic tree."""
        with connection.cursor() as cur:
            cur.execute("DELETE FROM codex_comicfts")
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _comicfts_join_type(qs) -> str:
        """Return the SQL join type Django assigned to ``codex_comicfts``."""
        for join in qs.query.alias_map.values():
            if getattr(join, "table_name", None) == "codex_comicfts":
                return getattr(join, "join_type", "")
        msg = "codex_comicfts not in alias_map"
        raise AssertionError(msg)

    @staticmethod
    def _left_outer_match_qs():
        """
        Return a queryset with ``codex_comicfts`` joined LEFT OUTER + MATCH.

        Django auto-promotes the FTS join to INNER as soon as ``MATCH`` is
        added to the WHERE. ``Query.promote_joins`` (the documented
        inverse of ``demote_joins``) flips it back to LEFT OUTER — the
        exact alias-map state ``force_inner_joins`` exists to prevent.
        """
        qs = Comic.objects.filter(comicfts__match="wonder")
        qs.query.promote_joins({"codex_comicfts"})
        return qs

    # ------------------------------------------------------------------
    # The contract under test
    # ------------------------------------------------------------------

    def test_left_joined_fts_match_raises_operational_error(self) -> None:
        """
        SQLite refuses ``MATCH`` against a LEFT-joined FTS5 table.

        Stripping the ``codex_comicfts`` demote re-introduces this error
        path on every FTS-enabled browse — exactly the failure mode that
        ``force_inner_joins`` exists to prevent.
        """
        qs = self._left_outer_match_qs()
        # Confirm the carrier query really does keep the join LEFT OUTER —
        # otherwise Django's auto-promotion would mask the regression we
        # care about.
        assert self._comicfts_join_type(qs) == "LEFT OUTER JOIN"
        with pytest.raises(OperationalError):
            list(qs.values_list("id", flat=True))

    def test_force_inner_joins_demotes_comicfts_when_fts_mode_true(self) -> None:
        """
        ``codex_comicfts`` is demoted to INNER JOIN when ``fts_mode`` is True.

        Carrier query: ``Comic.objects.values("comicfts__pk")`` puts the
        FTS table in the alias map as LEFT OUTER without any non-null
        filter — Django leaves it alone, so the demote is observable.
        """
        view = _FTSCallableView(fts_mode=True)
        qs = Comic.objects.values("comicfts__pk")
        assert self._comicfts_join_type(qs) == "LEFT OUTER JOIN"
        out = view.force_inner_joins(qs)
        assert self._comicfts_join_type(out) == "INNER JOIN"

    def test_force_inner_joins_skips_comicfts_when_fts_mode_false(self) -> None:
        """
        ``codex_comicfts`` stays LEFT OUTER when ``fts_mode`` is False.

        The non-FTS branch still demotes ``codex_library`` (and
        ``codex_comic`` for non-Comic models) — only the FTS table stays
        on the default LEFT OUTER JOIN, because no MATCH is being issued.
        """
        view = _FTSCallableView(fts_mode=False)
        qs = Comic.objects.values("comicfts__pk")
        assert self._comicfts_join_type(qs) == "LEFT OUTER JOIN"
        out = view.force_inner_joins(qs)
        assert self._comicfts_join_type(out) == "LEFT OUTER JOIN"

    def test_force_inner_joins_unblocks_match_on_left_joined_query(self) -> None:
        """
        End-to-end: ``force_inner_joins`` flips LEFT OUTER -> INNER and MATCH runs.

        Same carrier query as
        ``test_left_joined_fts_match_raises_operational_error``, but
        funneled through ``force_inner_joins(fts_mode=True)``. After the
        demote, ``codex_comicfts`` is INNER, MATCH succeeds, and the
        ``wonder`` token narrows the result to a single comic.
        """
        view = _FTSCallableView(fts_mode=True)
        qs = self._left_outer_match_qs()
        out = view.force_inner_joins(qs)
        assert self._comicfts_join_type(out) == "INNER JOIN"
        ids = list(out.values_list("id", flat=True))
        assert ids == [self.comic_wonder.pk], ids
