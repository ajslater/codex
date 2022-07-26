"""Cover Path functions."""
from pathlib import Path

from fnvhash import fnv1a_32

from codex.settings.settings import CODEX_PATH, ROOT_CACHE_PATH


COVER_ROOT = ROOT_CACHE_PATH / "covers"
MISSING_COVER_FN = "missing-cover.webp"
MISSING_COVER_PATH = CODEX_PATH / "img" / MISSING_COVER_FN
HEX_FILL = 8
PATH_STEP = 2
ZFILL = 12


def _hex_path(pk):
    """Translate an integer into an efficient filesystem path."""
    fnv = fnv1a_32(bytes(str(pk).zfill(ZFILL), "utf-8"))
    hex_str = "{0:0{1}x}".format(fnv, HEX_FILL)
    parts = []
    for i in range(0, len(hex_str), PATH_STEP):
        parts.append(hex_str[i : i + PATH_STEP])
    path = Path("/".join(parts))
    return path


def get_cover_path(pk):
    """Get cover path for comic pk."""
    cover_path = _hex_path(pk)
    return COVER_ROOT / cover_path.with_suffix(".webp")


def get_cover_paths(comic_pks):
    """Get cover paths for many comic pks."""
    cover_paths = set()
    for comic_pk in comic_pks:
        cover_path = get_cover_path(comic_pk)
        cover_paths.add(cover_path)
    return cover_paths
