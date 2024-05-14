"""Common view constants."""

from types import MappingProxyType

from codex.settings.settings import CODEX_PATH

FALSY = {None, "", "false", "0", False}
GROUP_NAME_MAP = MappingProxyType(
    {"p": "publisher", "i": "imprint", "s": "series", "v": "volume"}
)
STATIC_IMG_PATH = CODEX_PATH / "static_root/img"
MISSING_COVER_NAME_MAP = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        "f": "folder",
        "a": "story-arc",
    }
)
MISSING_COVER_FN = "missing-cover-165.webp"
MISSING_COVER_PATH = STATIC_IMG_PATH / MISSING_COVER_FN
