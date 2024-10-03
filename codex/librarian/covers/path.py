"""Cover Path functions."""

from pathlib import Path

from fnvhash import fnv1a_32

from codex.settings.settings import ROOT_CACHE_PATH


class CoverPathMixin:
    """Path methods for covers."""

    COVERS_ROOT = ROOT_CACHE_PATH / "covers"
    CUSTOM_COVERS_ROOT = ROOT_CACHE_PATH / "custom-covers"
    _HEX_FILL = 8
    _PATH_STEP = 2
    _ZFILL = 12

    @classmethod
    def _hex_path(cls, pk):
        """Translate an integer into an efficient filesystem path."""
        fnv = fnv1a_32(bytes(str(pk).zfill(cls._ZFILL), "utf-8"))
        hex_str = format(fnv, f"0{cls._ZFILL}x")
        parts = []
        for i in range(0, len(hex_str), cls._PATH_STEP):
            parts.append(hex_str[i : i + cls._PATH_STEP])
        return Path("/".join(parts))

    @classmethod
    def get_cover_path(cls, pk, custom=False):
        """Get cover path for comic pk."""
        cover_path = cls._hex_path(pk)
        root = cls.CUSTOM_COVERS_ROOT if custom else cls.COVERS_ROOT
        return root / cover_path.with_suffix(".webp")

    @classmethod
    def get_cover_paths(cls, pks, custom=False):
        """Get cover paths for many comic pks."""
        cover_paths = set()
        for pk in pks:
            cover_path = cls.get_cover_path(pk, custom)
            cover_paths.add(cover_path)
        return cover_paths
