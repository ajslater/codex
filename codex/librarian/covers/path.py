"""Cover Path functions."""

from pathlib import Path

from codex.settings import ROOT_CACHE_PATH


class CoverPathMixin:
    """Path methods for covers."""

    COVERS_ROOT = ROOT_CACHE_PATH / "covers"
    CUSTOM_COVERS_ROOT = ROOT_CACHE_PATH / "custom-covers"
    _HEX_FILL = 8
    _PATH_STEP = 2
    _ZFILL = 12

    @classmethod
    def _hex_path(cls, pk: int) -> Path:
        """Translate an integer into an efficient filesystem path."""
        hex_str = format(pk, f"0{cls._HEX_FILL}x")
        parts = [
            hex_str[i : i + cls._PATH_STEP]
            for i in range(0, len(hex_str), cls._PATH_STEP)
        ]
        return Path("/".join(parts))

    @classmethod
    def get_cover_path(cls, pk: int, *, custom: bool):
        """Get cover path for comic pk."""
        cover_path = cls._hex_path(pk)
        root = cls.CUSTOM_COVERS_ROOT if custom else cls.COVERS_ROOT
        return root / cover_path.with_suffix(".webp")

    @classmethod
    def get_cover_paths(cls, pks, *, custom: bool) -> set:
        """Get cover paths for many comic pks."""
        cover_paths = set()
        for pk in pks:
            cover_path = cls.get_cover_path(pk, custom=custom)
            cover_paths.add(cover_path)
        return cover_paths
