"""
KOReader document hashes.

``koreader_partial_md5`` ports KOReader's ``util.partialMD5``: up to twelve
1 KiB samples at offsets 0, 1024, 4096 … 1 GiB, stopping at the first offset
at or past EOF. These tests check it against a spelled-out reference over
files sized around every sample offset, and against KOReader's own test data
when ``KOREADER_TEST_DATA`` points at a koreader/test-data checkout.
"""

import hashlib
import os
from pathlib import Path
from typing import Final

import pytest

from codex.librarian.scribe.koreader_hash import (
    koreader_name_md5,
    koreader_partial_md5,
)

#: The offsets KOReader samples, written out rather than computed.
_OFFSETS: Final = (
    0,
    1024,
    4096,
    16384,
    65536,
    262144,
    1048576,
    4194304,
    16777216,
    67108864,
    268435456,
    1073741824,
)
_SAMPLE: Final = 1024
#: Sizes around the offsets a test can afford to write (sparse past 4 MiB).
_SIZES: Final = sorted(
    {0, 1, 1023, 1024, 1025, 2048}
    | {
        size
        for offset in _OFFSETS[2:9]
        for size in (offset - 1, offset, offset + 1, offset + _SAMPLE + 7)
    }
)
_UPSTREAM: Final = {
    "tall.pdf": "41cce710f34e5ec21315e19c99821415",
    "leaves.epub": "59d481d168cca6267322f150c5f6a2a3",
}


def _reference(data: bytes) -> str:
    md5 = hashlib.md5(usedforsecurity=False)
    for offset in _OFFSETS:
        if offset >= len(data):
            break
        md5.update(data[offset : offset + _SAMPLE])
    return md5.hexdigest()


def _content(size: int) -> bytes:
    """Deterministic bytes that differ at every sample."""
    block = bytes(range(251))
    return (block * (size // len(block) + 1))[:size]


@pytest.mark.parametrize("size", _SIZES)
def test_partial_md5_matches_reference(tmp_path: Path, size: int) -> None:
    """Every size around a sample offset hashes like the reference."""
    data = _content(size)
    path = tmp_path / "book.cbz"
    path.write_bytes(data)
    assert koreader_partial_md5(path) == _reference(data)


def test_twelfth_sample_at_one_gib(tmp_path: Path) -> None:
    """
    A file past 1 GiB takes the twelfth sample, which an 11-sample port drops.

    Sparse, so it costs no disk: only the marker bytes are written.
    """
    path = tmp_path / "huge.cbz"
    marker = b"twelfth-sample"
    with path.open("wb") as f:
        f.write(b"head")
        f.seek(_OFFSETS[-1])
        f.write(marker)
    with_marker = koreader_partial_md5(path)
    with path.open("r+b") as f:
        f.seek(_OFFSETS[-1])
        f.write(b"x" * len(marker))
    assert koreader_partial_md5(path) != with_marker


def test_empty_file_is_md5_of_nothing(tmp_path: Path) -> None:
    """No samples: the digest of zero bytes, as in Lua."""
    path = tmp_path / "empty.pdf"
    path.touch()
    assert koreader_partial_md5(path) == hashlib.md5(b"").hexdigest()  # noqa: S324


def test_name_md5_is_the_base_name_with_extension() -> None:
    """Filename matching hashes the UTF-8 base name only."""
    expected = hashlib.md5("Ñandú #1 (2024).cbz".encode()).hexdigest()  # noqa: S324
    assert koreader_name_md5("/comics/Ñandú/Ñandú #1 (2024).cbz") == expected


@pytest.mark.skipif(
    not os.environ.get("KOREADER_TEST_DATA"),
    reason="Set KOREADER_TEST_DATA to a koreader/test-data checkout.",
)
@pytest.mark.parametrize(("name", "expected"), sorted(_UPSTREAM.items()))
def test_upstream_vectors(name: str, expected: str) -> None:
    """KOReader's own expected hashes for its test files."""
    path = Path(os.environ["KOREADER_TEST_DATA"]) / name
    assert koreader_partial_md5(path) == expected
