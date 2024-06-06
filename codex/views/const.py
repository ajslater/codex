"""Common view constants."""

from datetime import datetime, timezone
from types import MappingProxyType

from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session

from codex.models import (
    AgeRating,
    BrowserGroupModel,
    Character,
    Comic,
    Contributor,
    ContributorPerson,
    ContributorRole,
    Country,
    Folder,
    Genre,
    Identifier,
    IdentifierType,
    Imprint,
    Language,
    Library,
    Location,
    OriginalFormat,
    Publisher,
    ScanInfo,
    Series,
    SeriesGroup,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
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
GROUP_ORDER = "rpisv"
MODEL_REL_MAP = MappingProxyType(
    {
        Publisher: "publisher",
        Imprint: "imprint",
        Series: "series",
        Volume: "volume",
        Folder: "parent_folder",
        StoryArc: "story_arc_numbers__story_arc",
        Comic: "pk",
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
GROUP_MODELS = (
    Publisher,
    Imprint,
    Series,
    Volume,
    Comic,
    Folder,
)
METADATA_MODELS = (
    AgeRating,
    Character,
    Country,
    Genre,
    Identifier,
    IdentifierType,
    Language,
    Location,
    OriginalFormat,
    SeriesGroup,
    ScanInfo,
    StoryArc,
    StoryArcNumber,
    Team,
    Tag,
    Tagger,
    Contributor,
    ContributorPerson,
    ContributorRole,
)
CONFIG_MODELS = (
    Library,
    User,
    Group,
    Session,
)
MAX_OBJ_PER_PAGE = 100
GROUP_MTIME_MODEL_MAP = MappingProxyType({"r": Publisher, "a": StoryArc, "f": Folder})
EPOCH_START = datetime.fromtimestamp(0, tz=timezone.utc)
