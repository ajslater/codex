"""Unit tests for fix_folder_relations (comic↔folder relation repair)."""

import shutil
from pathlib import Path
from typing import Final, override

from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.janitor.integrity.foreign_keys import fix_folder_relations
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.util import get_sort_name

_TMP_DIR: Final = Path("/tmp/codex.tests.folder_relations")  # noqa: S108


class FixFolderRelationsTests(TestCase):
    """fix_folder_relations re-derives every relation from comic.path."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(_TMP_DIR))
        self.publisher = Publisher.objects.create(name="P")
        self.imprint = Imprint.objects.create(name="I", publisher=self.publisher)
        self.series = Series.objects.create(
            name="S", publisher=self.publisher, imprint=self.imprint
        )
        self.volume = Volume.objects.create(
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

    def _comic(self, relpath: str, parent: Folder, ancestors: list[Folder]) -> Comic:
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
            file_type="CBZ",
        )
        comic.folders.set(ancestors)
        return comic

    def _ancestor_paths(self, comic: Comic) -> set[str]:
        comic.refresh_from_db()
        return set(comic.folders.values_list("path", flat=True))

    def _build_correct_tree(self):
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
        return {
            "root": root, "pub": pub, "s_a": s_a, "s_b": s_b, "s_c": s_c,
            "stale": stale, "c_a": c_a, "c_b": c_b, "c_c": c_c,
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
        assert recreated.parent_folder_id == t["pub"].pk
        assert recreated.sort_name == "series c"
        for comic in (t["c_a"], t["c_b"], t["c_c"]):
            self._assert_consistent(comic)
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
