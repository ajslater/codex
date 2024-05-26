"""Browser constants."""

from types import MappingProxyType

from codex.models import Folder, Publisher, StoryArc

MAX_OBJ_PER_PAGE = 100

GROUP_MTIME_MODEL_MAP = MappingProxyType({
    "r": Publisher,
    "a": StoryArc,
    "f": Folder
})
