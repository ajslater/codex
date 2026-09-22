"""Cover Path functions."""

from pathlib import Path

from codex.models import Comic, CustomCover
from codex.settings import ROOT_CACHE_PATH


class CoverPathMixin:
    """Path methods for covers."""

    COVERS_ROOT = ROOT_CACHE_PATH / "covers"
    CUSTOM_COVERS_ROOT = ROOT_CACHE_PATH / "custom-covers"
    _HEX_FILL = 8
    _PATH_STEP = 2
    _ZFILL = 12

    @classmethod
    def get_cover_root(cls, *, custom: bool) -> Path:
        """Get the cache root that holds a cover namespace's thumbs."""
        return cls.CUSTOM_COVERS_ROOT if custom else cls.COVERS_ROOT

    @staticmethod
    def get_cover_model(*, custom: bool) -> type[Comic] | type[CustomCover]:
        """Get the model whose rows own a cover namespace's thumbs."""
        return CustomCover if custom else Comic

    @staticmethod
    def get_cover_desc(*, custom: bool) -> str:
        """Get the log word for a cover namespace."""
        return "custom" if custom else "comic"

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
        root = cls.get_cover_root(custom=custom)
        return root / cover_path.with_suffix(".webp")

    @classmethod
    def get_cover_paths(cls, pks, *, custom: bool) -> set:
        """Get cover paths for many comic pks."""
        cover_paths = set()
        for pk in pks:
            cover_path = cls.get_cover_path(pk, custom=custom)
            cover_paths.add(cover_path)
        return cover_paths
