"""
KOReader document hashes for kosync progress sync.

KOReader identifies a book to a kosync server by one of two MD5 digests,
chosen per device under the plugin's "Document matching" setting:

* **Binary** — ``util.partialMD5``: an MD5 over up to twelve 1 KiB samples
  taken at offsets 0, 1024, 4096, 16384 … 1073741824 (``1024 << 2i`` for
  ``i`` in -1..10). LuaJIT's ``lshift(1024, -2)`` overflows to 0, which is
  where the first sample at offset 0 comes from. Sampling stops at the first
  offset at or past EOF.
* **Filename** — the MD5 of the file's base name, extension included.

The binary hash changes whenever the file's bytes do, so writing tags into an
archive breaks binary matching; the filename hash survives that.
"""

import hashlib
from pathlib import Path

_STEP = _SAMPLE_SIZE = 1024
# Lua ``for i = -1, 10``: twelve candidate samples.
_FIRST_I = -1
_LAST_I = 10


def _sample_offset(i: int) -> int:
    """Return the byte offset KOReader samples at for loop index ``i``."""
    return 0 if i < 0 else _STEP << (2 * i)


def koreader_partial_md5(path: str | Path) -> str:
    """Return KOReader's ``util.partialMD5`` of a file as lowercase hex."""
    md5 = hashlib.md5(usedforsecurity=False)
    with Path(path).open("rb") as f:
        for i in range(_FIRST_I, _LAST_I + 1):
            f.seek(_sample_offset(i))
            sample = f.read(_SAMPLE_SIZE)
            if not sample:
                break
            md5.update(sample)
    return md5.hexdigest()


def koreader_name_md5(path: str | Path) -> str:
    """Return the MD5 of a file's UTF-8 base name with extension."""
    name = Path(path).name
    return hashlib.md5(name.encode("utf-8"), usedforsecurity=False).hexdigest()
