"""
Unit tests for fix_folder_relations (comic↔folder relation repair).

The repair derives every relation from ``Comic.path``, and its prune step
deletes any folder it decides no comic lives under — a delete that
cascades comics and their bookmarks away with no existence probe. So the
rule for "is this path a comic" has to match the scanner's, which is
case-insensitive, and the prune has to refuse a folder a comic still
points at whatever that rule decides.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.janitor.integrity.foreign_keys import (
    _COMIC_SUFFIXES,
    _is_comic_path,
    fix_folder_relations,
)
from codex.models import (
    Bookmark,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.util import get_sort_name
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.folder_relations")


class FixFolderRelationsTests(TestCase):
    """fix_folder_relations re-derives every relation from comic.path."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(_TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="P")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="I", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="S", publisher=self.publisher, imprint=self.imprint
        )
        self.volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="1", publisher=self.publisher, imprint=self.imprint, series=self.series
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _folder(self, relpath: str, parent: Folder | None) -> Folder:
        path = _TMP_DIR / relpath if relpath else _TMP_DIR
        path.mkdir(parents=True, exist_ok=True)
        return Folder.objects.create(
            library=self.library,
            path=str(path),
            name=path.name,
            sort_name=get_sort_name(path.name),
            parent_folder=parent,
        )

    def _comic(
        self,
        relpath: str,
        parent: Folder,
        ancestors: list[Folder],
        file_type: str = "CBZ",
    ) -> Comic:
        path = _TMP_DIR / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        comic = Comic.objects.create(
            library=self.library,
            path=str(path),
            parent_folder=parent,
            issue_number=1,
            name=path.stem,
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            size=1,
            file_type=file_type,
        )
        comic.folders.set(ancestors)
        return comic

    def _ancestor_paths(self, comic: Comic) -> set[str]:
        comic.refresh_from_db()
        return set(comic.folders.values_list("path", flat=True))

    def _build_correct_tree(self) -> dict:
        """Create the correct folder tree + comics, then return key handles."""
        root = self._folder("", None)
        pub = self._folder("Marvel", root)
        s_a = self._folder("Marvel/Series A", pub)
        s_b = self._folder("Marvel/Series B", pub)
        s_c = self._folder("Marvel/Series C", pub)
        stale = self._folder("Marvel/Series Empty", pub)
        c_a = self._comic("Marvel/Series A/a.cbz", s_a, [root, pub, s_a])
        c_b = self._comic("Marvel/Series B/b.cbz", s_b, [root, pub, s_b])
        c_c = self._comic("Marvel/Series C/c.cbz", s_c, [root, pub, s_c])
        # The scanner imports an uppercase suffix verbatim, so the repair
        # has to recognize one. Part of the standard tree so every case
        # here covers it, including the migration-registry path.
        s_u = self._folder("Marvel/Series Upper", pub)
        c_u = self._comic("Marvel/Series Upper/u.CBZ", s_u, [root, pub, s_u])
        return {
            "root": root, "pub": pub, "s_a": s_a, "s_b": s_b, "s_c": s_c,
            "stale": stale, "c_a": c_a, "c_b": c_b, "c_c": c_c,
            "s_u": s_u, "c_u": c_u,
        }  # fmt: skip

    def _corrupt(self, t: dict) -> None:
        """Reproduce the observed drift: swapped FKs+M2M, a missing folder, a stale one."""
        root, pub, s_a, s_b = t["root"], t["pub"], t["s_a"], t["s_b"]
        c_a, c_b, c_c = t["c_a"], t["c_b"], t["c_c"]
        # Swap A and B (FK points at a real-but-wrong folder; M2M leaf wrong).
        Comic.objects.filter(pk=c_a.pk).update(parent_folder=s_b)
        c_a.folders.set([root, pub, s_b])
        Comic.objects.filter(pk=c_b.pk).update(parent_folder=s_a)
        c_b.folders.set([root, pub, s_a])
        # C: repoint off its real folder, then delete that folder so the
        # correct target is *missing* (must be recreated). Repoint BEFORE
        # delete so the CASCADE on parent_folder doesn't take C with it.
        Comic.objects.filter(pk=c_c.pk).update(parent_folder=s_a)
        c_c.folders.set([root, pub, s_a])
        t["s_c"].delete()

    def _assert_consistent(self, comic: Comic) -> None:
        """Assert the comic's FK and M2M match the ancestor chain from its path."""
        comic.refresh_from_db()
        parent = Path(comic.path).parent
        assert comic.parent_folder is not None
        assert comic.parent_folder.path == str(parent)
        expected = set()
        node = parent
        while True:
            expected.add(str(node))
            if str(node) == str(_TMP_DIR):
                break
            node = node.parent
        assert self._ancestor_paths(comic) == expected

    def _assert_repaired(self, t: dict) -> None:
        """Post-heal invariants: missing folder back, comics consistent, stale gone."""
        recreated = Folder.objects.get(path=str(_TMP_DIR / "Marvel" / "Series C"))
        assert recreated.parent_folder is not None
        assert recreated.parent_folder.pk == t["pub"].pk
        assert recreated.sort_name == "series c"
        for comic in (t["c_a"], t["c_b"], t["c_c"], t["c_u"]):
            self._assert_consistent(comic)
        # The uppercase comic's folder is not "empty".
        assert Folder.objects.filter(pk=t["s_u"].pk).exists()
        assert not Folder.objects.filter(
            path=str(_TMP_DIR / "Marvel" / "Series Empty")
        ).exists()

    def test_full_repair(self) -> None:
        """Create missing, repoint FK, rebuild M2M, prune stale — all from path."""
        t = self._build_correct_tree()
        self._corrupt(t)

        result = fix_folder_relations(logger)

        self._assert_repaired(t)
        assert result["created"] == 1
        assert result["pruned"] == 1
        # All three corrupted comics were repointed.
        assert result["repointed"] == len((t["c_a"], t["c_b"], t["c_c"]))

    def test_idempotent_on_clean_db(self) -> None:
        """A second run (already-consistent DB) changes nothing."""
        t = self._build_correct_tree()
        self._corrupt(t)
        fix_folder_relations(logger)

        result = fix_folder_relations(logger)

        assert result == {
            "created": 0,
            "repointed": 0,
            "m2m_added": 0,
            "m2m_removed": 0,
            "pruned": 0,
        }

    def test_prune_false_keeps_empty_folders(self) -> None:
        """prune=False leaves stale folders in place but still fixes relations."""
        t = self._build_correct_tree()
        self._corrupt(t)

        result = fix_folder_relations(logger, prune=False)

        assert result["pruned"] == 0
        assert Folder.objects.filter(
            path=str(_TMP_DIR / "Marvel" / "Series Empty")
        ).exists()

    def test_repair_via_migration_apps_registry(self) -> None:
        """
        The migration code path (historical models) repairs identically.

        Folder creation under the historical model runs base ``save()`` —
        no ``presave``/``set_stat`` and no auto ``sort_name`` — so this
        also proves the explicit ``sort_name`` and the no-filesystem path.
        """
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        t = self._build_correct_tree()
        self._corrupt(t)

        historical_apps = MigrationLoader(connection).project_state().apps
        result = fix_folder_relations(logger, apps_registry=historical_apps)

        self._assert_repaired(t)
        assert result["created"] == 1
        assert result["pruned"] == 1


class ComicSuffixTests(TestCase):
    """The suffix rule must match the scanner's, which ignores case."""

    def test_suffixes_are_derived_from_comicbox(self) -> None:
        """A new archive format in comicbox must not be left behind here."""
        assert frozenset({".cbz", ".cbr", ".cb7", ".cbt", ".pdf"}) == _COMIC_SUFFIXES, (
            _COMIC_SUFFIXES
        )

    def test_comic_paths_are_recognized_in_any_case(self) -> None:
        """The importer stores whatever case the filesystem had."""
        for path in (
            "/c/a.cbz",
            "/c/a.CBZ",
            "/c/a.Cbr",
            "/c/a.PDF",
            "/c/a.cb7",
            "/c/A Series (2019)/a.CBT",
        ):
            assert _is_comic_path(path), path

    def test_non_comic_paths_are_rejected(self) -> None:
        """Directory rows and stray files still fall out."""
        for path in ("/c/a.txt", "/c/Series", "/c/a.cbz.part", "/c/notes.pdf.bak"):
            assert not _is_comic_path(path), path


class PrunePreservesLiveFoldersTests(FixFolderRelationsTests):
    """The prune deletes rows that cascade bookmarks; it gets two guards."""

    def test_uppercase_extension_folder_survives_prune(self) -> None:
        """The bug: a whole publisher pruned for having uppercase suffixes."""
        t = self._build_correct_tree()
        user = User.objects.create_user(username="reader", password="x")  # noqa: S106
        bookmark = Bookmark.objects.create(user=user, comic=t["c_u"], finished=True)

        result = fix_folder_relations(logger)

        assert Folder.objects.filter(pk=t["s_u"].pk).exists()
        assert Comic.objects.filter(pk=t["c_u"].pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk).exists()
        # Only the genuinely empty folder goes.
        assert result["pruned"] == 1
        self._assert_consistent(t["c_u"])

    def test_uppercase_comic_with_drifted_parent_is_repointed(self) -> None:
        """An uppercase comic was skipped by the repoint step too."""
        t = self._build_correct_tree()
        Comic.objects.filter(pk=t["c_u"].pk).update(parent_folder=t["s_a"])
        t["c_u"].folders.set([t["root"], t["pub"], t["s_a"]])

        fix_folder_relations(logger)

        self._assert_consistent(t["c_u"])

    def test_folder_referenced_by_a_comic_is_never_pruned(self) -> None:
        """The backstop: a suffix rule can be wrong again; this cannot."""
        t = self._build_correct_tree()
        odd = self._folder("Marvel/Series Odd", t["pub"])
        # A suffix no rule recognizes, so it contributes no needed folder.
        comic = self._comic(
            "Marvel/Series Odd/odd.cbx", odd, [t["root"], t["pub"], odd]
        )

        fix_folder_relations(logger)

        assert Folder.objects.filter(pk=odd.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()
