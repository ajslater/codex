"""Common view constants."""

from types import MappingProxyType

from codex.models import (
    BrowserGroupModel,
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
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


ROOT_GROUP = "r"
FOLDER_GROUP = "f"
STORY_ARC_GROUP = "a"
COMIC_GROUP = "c"
GROUP_RELATION = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
        STORY_ARC_GROUP: "story_arc_numbers__story_arc",
    }
)
GROUP_MODEL_MAP: MappingProxyType[str, type[BrowserGroupModel] | None] = (
    MappingProxyType(
        {
            ROOT_GROUP: None,
            "p": Publisher,
            "i": Imprint,
            "s": Series,
            "v": Volume,
            COMIC_GROUP: Comic,
            FOLDER_GROUP: Folder,
            STORY_ARC_GROUP: StoryArc,
        }
    )
)
