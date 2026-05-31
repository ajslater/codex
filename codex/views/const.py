"""Common view constants."""

from datetime import UTC, datetime
from types import MappingProxyType

from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db.models.expressions import Value
from django.db.models.fields import DateTimeField, PositiveSmallIntegerField

from codex.group import Group
from codex.models import (
    AgeRating,
    BrowserGroupModel,
    Character,
    Comic,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Identifier,
    IdentifierSource,
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
    Universe,
    Volume,
)
from codex.settings import CODEX_PATH

# Legacy single-char group constants, now sourced from the Group enum.
# Each still compares equal to its char (StrEnum), so existing
# ``group == ROOT_GROUP`` checks are unaffected.
ROOT_GROUP = Group.ROOT
FOLDER_GROUP = Group.FOLDER
STORY_ARC_GROUP = Group.ARC
COMIC_GROUP = Group.COMIC
GROUP_NAME_MAP = MappingProxyType(
    {
        Group.PUBLISHER: "publisher",
        Group.IMPRINT: "imprint",
        Group.SERIES: "series",
        Group.VOLUME: "volume",
    }
)
STATIC_IMG_PATH = CODEX_PATH / "static/img"
MISSING_COVER_NAME_MAP = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        FOLDER_GROUP: "folder",
        STORY_ARC_GROUP: "story-arc",
    }
)
MISSING_COVER_FN = "comic-165.webp"
MISSING_COVER_PATH = STATIC_IMG_PATH / MISSING_COVER_FN

GROUP_RELATION = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
        STORY_ARC_GROUP: "story_arc_numbers__story_arc",
    }
)
FILTER_ONLY_GROUP_RELATION = MappingProxyType(
    {
        **GROUP_RELATION,
        FOLDER_GROUP: "folders",
    }
)
METADATA_GROUP_RELATION = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        COMIC_GROUP: "comic",
        FOLDER_GROUP: "comic__folders",
        STORY_ARC_GROUP: "comic__story_arc_numbers__story_arc",
    }
)
CUSTOM_COVER_GROUP_RELATION = MappingProxyType(
    {**GROUP_NAME_MAP, FOLDER_GROUP: "folder", STORY_ARC_GROUP: "storyarc"}
)
# Publisher-hierarchy nav ordering (root → volume) as a string of legacy
# char codes, kept for the substring/index checks in browser settings.
GROUP_ORDER = "".join(
    g.char
    for g in (Group.ROOT, Group.PUBLISHER, Group.IMPRINT, Group.SERIES, Group.VOLUME)
)
MODEL_REL_MAP: MappingProxyType[type[BrowserGroupModel], str] = MappingProxyType(
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
            Group.ROOT: None,
            Group.PUBLISHER: Publisher,
            Group.IMPRINT: Imprint,
            Group.SERIES: Series,
            Group.VOLUME: Volume,
            Group.COMIC: Comic,
            Group.FOLDER: Folder,
            Group.ARC: StoryArc,
        }
    )
)
GROUP_MODELS = (
    Publisher,
    Imprint,
    Series,
    Volume,
    Folder,
    StoryArc,
)
STATS_GROUP_MODELS = (
    *GROUP_MODELS,
    Comic,
)
METADATA_MODELS = (
    AgeRating,
    Character,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Genre,
    Identifier,
    IdentifierSource,
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
    Universe,
)
CONFIG_MODELS = (
    Library,
    User,
    AuthGroup,
    Session,
)
GROUP_MTIME_MODEL_MAP = MappingProxyType(
    {Group.ROOT: Publisher, Group.ARC: StoryArc, Group.FOLDER: Folder}
)
EPOCH_START = datetime.fromtimestamp(0, tz=UTC)
ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
NONE_INTEGERFIELD = Value(None, PositiveSmallIntegerField())
NONE_DATETIMEFIELD = Value(None, DateTimeField())
EPOCH_START_DATETIMEFIELD = Value(EPOCH_START)
