"""
A conversion whose destination is taken is refused before any work.

Writing tags to a CBR repacks it as a CBZ at a new path. With "delete
original" off, the CBR stays in the library beside the CBZ its own first
write produced, and every later write on that CBR collides with it.

comicbox does refuse the collision — but only after opening the archive,
merging the metadata and serializing it, and its message names a
filename with no hint of what to do about it. Because tag-write errors
dedupe by path, that vaguer message also replaced the clearer one the
planner had already recorded.

Refusing in codex means the comic never reaches ``bulk_write``, so there
is exactly one message per path and it can say what to do. Codex's check
is the database-aware one; comicbox's remains the filesystem backstop
for in-batch collisions codex does not model.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.test import TestCase

from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tagwrite_errors import (
    clear_tag_write_errors,
    get_tag_write_errors,
)
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic
from tests.test_tag_writer_rename import (
    _COMICBOX_TARGET,
    _TMP_DIR,
    _FakeComicbox,
    _FakeQueue,
    _make_comic,
    _make_writer,
)

_BULK_WRITE_TARGET: Final = "codex.librarian.scribe.tag_writer.bulk_write"
_PATCH: Final = {"series": {"name": "S"}}


def _errors_for(path: Path) -> list[str]:
    """Every tag-write error recorded against a path."""
    return [
        error["error"] for error in get_tag_write_errors() if error["path"] == str(path)
    ]


class _PreflightTestBase(TestCase):
    """A CBR comic, with the tag-write error store cleared around it."""

    @override
    def setUp(self) -> None:
        # The temp library is shared across this module and the rename
        # tests, and half of these cases turn on which files exist.
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, _TMP_DIR, ignore_errors=True)
        clear_tag_write_errors()
        self.addCleanup(clear_tag_write_errors)
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.writer = _make_writer(self.queue)  # pyright: ignore[reportUninitializedInstanceVariable]

    def _write(self, comic: Comic, **task_kwargs) -> list:
        """Run a tag write with bulk_write stubbed, returning its items."""
        seen: list = []

        def fake_bulk_write(items, **_kwargs):
            seen.extend(items)
            return iter(())

        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch=_PATCH,
            **task_kwargs,
        )
        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch(_BULK_WRITE_TARGET, fake_bulk_write),
        ):
            self.writer.write_tags(task)
        return seen


class TagWriterTwinRefusalTests(_PreflightTestBase):
    """A CBR that has already been converted refuses, and says why."""

    def test_twin_with_a_row_names_it_and_never_writes(self) -> None:
        """The reporter's case: convert once, then write the CBR again."""
        comic = _make_comic(events=False, name="Foo.cbr")
        twin = _make_comic(
            events=False, name="Foo.cbz", issue_number=2, library=comic.library
        )

        items = self._write(comic, delete_original=False, rename=False)

        assert not items, "the refused comic reached comicbox"
        errors = _errors_for(Path(comic.path))
        assert len(errors) == 1, errors
        assert "already converted to Foo.cbz" in errors[0]
        assert "edit that comic's tags instead" in errors[0]
        assert Comic.objects.filter(pk=twin.pk).exists()

    def test_the_message_is_stable_across_runs(self) -> None:
        """
        Errors dedupe by path, so the last writer of a message wins.

        comicbox's vaguer text used to replace this one on every retry.
        """
        comic = _make_comic(events=False, name="Foo.cbr")
        _make_comic(events=False, name="Foo.cbz", issue_number=2, library=comic.library)

        self._write(comic, delete_original=False, rename=False)
        first = _errors_for(Path(comic.path))
        self._write(comic, delete_original=False, rename=False)
        second = _errors_for(Path(comic.path))

        assert first == second, (first, second)

    def test_an_orphan_twin_gets_the_other_message(self) -> None:
        """A CBZ on disk with no row cannot be "edited instead"."""
        comic = _make_comic(events=False, name="Bar.cbr")
        (_TMP_DIR / "Bar.cbz").write_text("orphan")

        items = self._write(comic, delete_original=False, rename=False)

        assert not items
        errors = _errors_for(Path(comic.path))
        assert len(errors) == 1, errors
        assert "conversion destination already exists: Bar.cbz" in errors[0]

    def test_a_free_destination_is_written(self) -> None:
        """Nothing in the way, nothing refused."""
        comic = _make_comic(events=False, name="Free.cbr")

        items = self._write(comic, delete_original=False, rename=False)

        assert [item.path for item in items] == [Path(comic.path)]
        assert not _errors_for(Path(comic.path))

    def test_an_in_place_write_is_never_refused(self) -> None:
        """A CBZ writes in place, so its own path is not a collision."""
        comic = _make_comic(events=False, name="Plain.cbz")

        items = self._write(comic, delete_original=False, rename=False)

        assert [item.path for item in items] == [Path(comic.path)]
        assert not _errors_for(Path(comic.path))

    def test_the_file_type_decides_not_the_suffix(self) -> None:
        """A CBZ misnamed .cbr writes in place; the row knows better."""
        comic = _make_comic(events=False, name="Mislabeled.cbr", file_type="CBZ")
        (_TMP_DIR / "Mislabeled.cbz").write_text("not a twin")

        items = self._write(comic, delete_original=False, rename=False)

        assert [item.path for item in items] == [Path(comic.path)]
        assert not _errors_for(Path(comic.path))


class TagWriterRenameTwinTests(_PreflightTestBase):
    """With rename on, the scheme name is the destination that matters."""

    def test_a_scheme_named_twin_is_refused(self) -> None:
        """
        Kept originals are renamed after the write, freeing the plain name.

        Without checking the scheme name too, every later write converts
        again and mints another copy.
        """
        comic = _make_comic(events=False, name="Keep.cbr")
        # The name _FakeComicbox predicts, already taken by the first run.
        (_TMP_DIR / "Renamed #001.cbz").write_text("the first conversion")

        items = self._write(comic, delete_original=False, rename=True)

        assert not items
        errors = _errors_for(Path(comic.path))
        assert len(errors) == 1, errors
        assert "Renamed #001.cbz" in errors[0]

    def test_deleting_the_original_moves_the_stem_first(self) -> None:
        """
        The rename runs before the write, so the old stem is not the target.

        Refusing on the pre-rename path would block a write that
        succeeds.
        """
        comic = _make_comic(events=False, name="Move.cbr")
        # Occupies the *old* stem's destination only.
        (_TMP_DIR / "Move.cbz").write_text("not in the way")

        items = self._write(comic, delete_original=True, rename=True)

        assert items, _errors_for(Path(comic.path))
        # Written at the renamed path, which still carries the .cbr suffix.
        assert items[0].path.name == "Renamed #001.cbr"


class TagWriterRenameOnlyTests(_PreflightTestBase):
    """A task with nothing to write converts nothing."""

    def test_a_rename_only_task_is_not_refused(self) -> None:
        """No patch means no write, so no conversion to collide."""
        comic = _make_comic(events=False, name="Solo.cbr")
        (_TMP_DIR / "Solo.cbz").write_text("would collide if we wrote")

        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)
        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch(_BULK_WRITE_TARGET, side_effect=AssertionError("wrote anyway")),
        ):
            self.writer.write_tags(task)

        assert "already converted" not in " ".join(_errors_for(Path(comic.path)))


class TagWriterKeptConversionCollisionTests(_PreflightTestBase):
    """A kept conversion that cannot take its scheme name says so."""

    def test_a_taken_scheme_name_is_reported(self) -> None:
        """It used to keep its old name silently, leaving a mystery file."""
        comic = _make_comic(events=False, name="Quiet.cbr")
        queue = _FakeQueue()
        writer = _make_writer(queue)
        converted = _TMP_DIR / "Quiet.cbz"
        taken = _TMP_DIR / "Renamed #001.cbz"
        taken.write_text("already here")

        def fake_write(_self, _task, _current_paths):
            converted.write_text("converted")
            return {comic.pk: converted}

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(TagWriter, "_write", fake_write),
        ):
            writer.write_tags(
                BulkTagWriteTask(
                    comic_pks=frozenset({comic.pk}),
                    patch=_PATCH,
                    delete_original=False,
                    rename=True,
                )
            )

        errors = _errors_for(converted)
        assert errors, get_tag_write_errors()
        assert "keeps its old name" in errors[0]
