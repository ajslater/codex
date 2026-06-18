"""Tests for the xz backup helpers."""

from __future__ import annotations

import lzma
import re
import shutil
from pathlib import Path
from typing import Final, override

from django.test import TestCase

from codex.xz import (
    compress_path_to_xz,
    date_stamp,
    prune_dated,
    read_text_maybe_xz,
    write_xz_bytes,
    xz_preset,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.compression")  # noqa: S108
_GiB: Final = 1024**3
_FULL_PRESET: Final = 9
_MIN_MIDRANGE_PRESET: Final = 5


class CompressionTests(TestCase):
    """write/read/prune round-trips."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_write_xz_bytes_round_trips_and_leaves_no_tmp(self) -> None:
        dest = _TMP_DIR / "blob.bin.xz"
        payload = b"sqlite-ish bytes \x00\x01\x02" * 1000
        write_xz_bytes(payload, dest, preset=1)
        assert dest.is_file()
        with lzma.open(dest, "rb") as src:
            assert src.read() == payload
        # The atomic temp must be cleaned up.
        assert not (_TMP_DIR / "blob.bin.xz.tmp").exists()

    def test_compress_path_to_xz_round_trips(self) -> None:
        src = _TMP_DIR / "src.bin"
        payload = bytes(range(256)) * 4096
        src.write_bytes(payload)
        dest = _TMP_DIR / "src.bin.xz"
        compress_path_to_xz(src, dest, preset=1)
        with lzma.open(dest, "rb") as out:
            assert out.read() == payload
        assert not (_TMP_DIR / "src.bin.xz.tmp").exists()

    def test_xz_preset_scales_with_memory(self) -> None:
        # A roomy budget earns the richest preset; a tiny one floors at 0.
        assert xz_preset(64 * _GiB) == _FULL_PRESET
        assert xz_preset(1 * _GiB) >= _MIN_MIDRANGE_PRESET  # ~256 MiB encoder budget
        assert xz_preset(1024) == 0  # nothing fits but the floor

    def test_read_text_maybe_xz(self) -> None:
        plain = _TMP_DIR / "a.sql"
        plain.write_text("SELECT 1;\n", encoding="utf-8")
        assert read_text_maybe_xz(plain) == "SELECT 1;\n"

        compressed = _TMP_DIR / "a.sql.xz"
        with lzma.open(compressed, "wt", encoding="utf-8") as out:
            out.write("SELECT 2;\n")
        assert read_text_maybe_xz(compressed) == "SELECT 2;\n"

    def test_prune_dated_keeps_newest(self) -> None:
        pattern = r"^db\.\d{4}-\d{2}-\d{2}\.bak\.xz$"
        for day in range(1, 6):
            (_TMP_DIR / f"db.2020-01-0{day}.bak.xz").write_bytes(b"x")
        # A non-matching sibling must be left untouched.
        (_TMP_DIR / "db.before-v1.bak.xz").write_bytes(b"keep")

        prune_dated(_TMP_DIR, pattern, keep=2)

        remaining = sorted(p.name for p in _TMP_DIR.glob("db.*"))
        assert remaining == [
            "db.2020-01-04.bak.xz",
            "db.2020-01-05.bak.xz",
            "db.before-v1.bak.xz",
        ]

    def test_prune_dated_missing_dir_is_noop(self) -> None:
        prune_dated(_TMP_DIR / "nope", r".*")  # must not raise

    def test_date_stamp_is_iso(self) -> None:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_stamp())
