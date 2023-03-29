"""Cover Path functions."""
from pathlib import Path

from fnvhash import fnv1a_32

from codex.settings.settings import CODEX_PATH, ROOT_CACHE_PATH
from codex.threads import QueuedThread


class CoverPathMixin(QueuedThread):
    """Path methods for covers."""

    COVER_ROOT = ROOT_CACHE_PATH / "covers"
    MISSING_COVER_PATH = CODEX_PATH / "img" / "missing-cover.webp"
    _HEX_FILL = 8
    _PATH_STEP = 2
    _ZFILL = 12

    @classmethod
    def _hex_path(cls, pk):
        """Translate an integer into an efficient filesystem path."""
        fnv = fnv1a_32(bytes(str(pk).zfill(cls._ZFILL), "utf-8"))
        hex_str = "{0:0{1}x}".format(fnv, cls._HEX_FILL)
        parts = []
        for i in range(0, len(hex_str), cls._PATH_STEP):
            parts.append(hex_str[i : i + cls._PATH_STEP])
        return Path("/".join(parts))

    @classmethod
    def get_cover_path(cls, pk):
        """Get cover path for comic pk."""
        cover_path = cls._hex_path(pk)
        return cls.COVER_ROOT / cover_path.with_suffix(".webp")

    @classmethod
    def get_cover_paths(cls, comic_pks):
        """Get cover paths for many comic pks."""
        cover_paths = set()
        for comic_pk in comic_pks:
            cover_path = cls.get_cover_path(comic_pk)
            cover_paths.add(cover_path)
        return cover_paths
