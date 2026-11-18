"""
KOReader hashing at import follows the KOReader Sync flag.

The hashes live beside Comic, in ``ComicKoreaderHash``, so they stay out of
the metadata API, collection metadata and search, and migration 0060 leaves
the Comic table alone.

``Comic.presave`` read every file for KOReader's partial MD5 on every
create, update and move, with KOReader Sync off (the default). Both hash
columns were in the no-op re-import check, so after the upgrade (NULL
hashes everywhere) the first forced or lazy re-import of an unchanged
comic rewrote it, purged its cover and reloaded every browser: the #992
loop's guard, defeated once per comic.
"""

import shutil
import zipfile
from importlib import import_module
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.koreader_hash import (
    koreader_name_md5,
    koreader_partial_md5,
)
from codex.models import (
    AdminFlag,
    Comic,
    ComicKoreaderHash,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import codex_init
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.metadata.const import COMIC_VALUE_FIELD_NAMES
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"
_TAGS: Final = "comicbox:\n  series:\n    name: S\n"
_NEW_TAGS: Final = "comicbox:\n  series:\n    name: S\n  title: Changed\n"
# The Comic columns the hashes had before they moved beside it.
_OLD_HASH_FIELDS: Final = ("koreader_hash", "koreader_name_hash")
_PARTIAL_MD5: Final = "codex.models.koreader.koreader_partial_md5"


def _set_flag(*, on: bool) -> None:
    AdminFlag.objects.filter(key=AdminFlagChoices.KOREADER_SYNC.value).update(on=on)
    cache.clear()


def _hashes(path: str) -> tuple[str | None, str | None] | None:
    """Return a comic's ``(binary, name)`` hashes, None for no row."""
    row = (
        ComicKoreaderHash.objects.filter(comic__path=path)
        .values_list("binary_hash", "name_hash")
        .first()
    )
    return tuple(row) if row else None


class TestKoreaderHashImport(TestCase):
    """The binary hash is read only with the flag on; the name hash always."""

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()

    @override
    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(TMP_DIR, ignore_errors=True)
        finally:
            super().tearDownClass()

    @override
    def setUp(self):
        cache.clear()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=TMP_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        cache.clear()

    @staticmethod
    def _write(name: str, tags: str = _TAGS) -> str:
        path = TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", tags)
            zf.writestr("page0.jpg", _PAGE)
        return str(path)

    def _importer(self, task: ImportTask, queue: MagicMock) -> ComicImporter:
        return ComicImporter(task, logger, queue, Lock(), Event())

    def _import(self, task: ImportTask) -> MagicMock:
        queue = MagicMock()
        importer = self._importer(task, queue)
        assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()
        importer.finish()
        return queue

    def _scan(self, *paths: str) -> None:
        self._import(
            ImportTask(library_id=self.library.pk, files_created=frozenset(paths))
        )

    def _force(self, path: str) -> MagicMock:
        return self._import(
            ImportTask(
                library_id=self.library.pk,
                files_modified=frozenset({path}),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
        )

    def test_flag_off_reads_no_file_for_the_binary_hash(self) -> None:
        _set_flag(on=False)
        path = self._write("off.cbz")
        with patch(_PARTIAL_MD5, side_effect=AssertionError("read the file")):
            self._scan(path)
        assert _hashes(path) == (None, koreader_name_md5(path))

    def test_flag_on_hashes_the_file(self) -> None:
        _set_flag(on=True)
        path = self._write("on.cbz")
        self._scan(path)
        assert _hashes(path) == (koreader_partial_md5(path), koreader_name_md5(path))

    def test_the_flag_is_read_once_per_import(self) -> None:
        _set_flag(on=True)
        paths = [self._write(f"many{n}.cbz") for n in range(3)]
        with patch(
            "codex.librarian.scribe.importer.init.koreader_sync_enabled",
            return_value=True,
        ) as flag:
            self._scan(*paths)
        assert flag.call_count == 1
        assert ComicKoreaderHash.objects.filter(binary_hash__isnull=False).count() == 3  # noqa: PLR2004

    def test_an_update_with_the_flag_off_nulls_the_binary_hash(self) -> None:
        """The backfill hashes only null rows, so a stale hash is not kept."""
        _set_flag(on=True)
        path = self._write("updated.cbz")
        self._scan(path)
        _set_flag(on=False)
        self._write("updated.cbz", _NEW_TAGS)
        self._force(path)
        assert Comic.objects.get(path=path).name == "Changed"
        assert _hashes(path) == (None, koreader_name_md5(path))

    def test_unchanged_comic_with_no_hashes_is_a_noop(self) -> None:
        """The state every comic is in after the 0060 upgrade."""
        _set_flag(on=False)
        path = self._write("upgraded.cbz")
        self._scan(path)
        ComicKoreaderHash.objects.all().delete()
        updated_at = Comic.objects.get(path=path).updated_at

        queue = self._force(path)

        queued = [call.args[0] for call in queue.put.call_args_list]
        assert LIBRARY_CHANGED_TASK not in queued, queued
        assert Comic.objects.get(path=path).updated_at == updated_at

    def test_a_move_updates_only_the_name_hash(self) -> None:
        """The file is unchanged, so its binary hash is kept and not re-read."""
        _set_flag(on=True)
        path = self._write("before.cbz")
        self._scan(path)
        binary = koreader_partial_md5(path)
        new_path = str(TMP_DIR / "after.cbz")
        shutil.move(path, new_path)
        task = ImportTask(library_id=self.library.pk, files_moved={path: new_path})
        with patch(_PARTIAL_MD5, side_effect=AssertionError("read the file")):
            self._importer(task, MagicMock()).move_and_modify_dirs()
        assert _hashes(new_path) == (binary, koreader_name_md5(new_path))

    def test_deleting_a_comic_deletes_its_hashes(self) -> None:
        _set_flag(on=True)
        path = self._write("gone.cbz")
        self._scan(path)
        assert _hashes(path)
        Comic.objects.filter(path=path).delete()
        assert not ComicKoreaderHash.objects.exists()


class TestKoreaderHashesStayInternal(TestCase):
    """Neither hash is metadata, a collection value or a search field."""

    @override
    def setUp(self) -> None:
        cache.clear()
        codex_init()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=TMP_DIR)
        path = TMP_DIR / "md.cbz"
        path.write_bytes(b"x" * 300)
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=path,
            issue_number=1,
            name="md",
            size=1,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
        )
        ComicKoreaderHash.compute(self.comic.pk, path, binary=True).save()
        user = User.objects.create_user(username="md", password="x", is_staff=True)  # noqa: S106
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def test_metadata_response_has_no_hashes(self) -> None:
        response = self.client.get(f"/api/v4/browse/comics/{self.comic.pk}/metadata")
        assert response.status_code == 200, response.content  # noqa: PLR2004
        body = response.content.decode()
        for key in ("koreaderHash", "koreaderNameHash", "binaryHash", "nameHash"):
            assert key not in body
        for digest in ComicKoreaderHash.objects.values_list(
            "binary_hash", "name_hash"
        ).get():
            assert digest not in body

    def test_collection_metadata_does_not_aggregate_them(self) -> None:
        assert not {*_OLD_HASH_FIELDS, "koreader"} & COMIC_VALUE_FIELD_NAMES

    def test_comic_has_no_koreader_field(self) -> None:
        names = {field.name for field in Comic._meta.get_fields()}
        assert not {name for name in names if "koreader" in name}


@pytest.mark.parametrize("field", [*_OLD_HASH_FIELDS, "koreader"])
def test_hashes_are_not_search_fields(field: str) -> None:
    """Neither hash can be named in a field search."""
    with pytest.raises(ValueError, match="Unknown field"):
        parse_field(field)


def test_0060_leaves_the_comic_table_alone() -> None:
    """A v2.6.0 upgrade must not rewrite the widest table for KOReader."""
    migration = import_module("codex.migrations.0060_post_v2_6_0_schema").Migration
    touched = [
        operation
        for operation in migration.operations
        if getattr(operation, "model_name", None) == "comic"
        or getattr(operation, "name", None) == "Comic"
    ]
    assert not touched
