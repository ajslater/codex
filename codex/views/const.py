"""Common view constants."""

from datetime import UTC, datetime
from types import MappingProxyType

from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db.models.expressions import Value
from django.db.models.fields import DateTimeField, PositiveSmallIntegerField

from codex.collection import Collection
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

# Legacy single-char group constants, now sourced from the Collection enum.
# Each still compares equal to its char (StrEnum), so existing
# ``group == ROOT_GROUP`` checks are unaffected.
ROOT_GROUP = Collection.ROOT
FOLDER_GROUP = Collection.FOLDER
STORY_ARC_GROUP = Collection.ARC
COMIC_GROUP = Collection.COMIC
GROUP_NAME_MAP = MappingProxyType(
    {
        Collection.PUBLISHER: "publisher",
        Collection.IMPRINT: "imprint",
        Collection.SERIES: "series",
        Collection.VOLUME: "volume",
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

# Annotated ``[str, str]`` (not ``[Collection, str]``): the keys are Collection members
# but lookups come in as their collection-value string (Collection is a StrEnum, so
# both resolve to the same bucket). The explicit annotation lets str-typed
# group values index these maps without a type error.
GROUP_RELATION: MappingProxyType[str, str] = MappingProxyType(
    {
        **GROUP_NAME_MAP,
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
        STORY_ARC_GROUP: "story_arc_numbers__story_arc",
    }
)
FILTER_ONLY_GROUP_RELATION: MappingProxyType[str, str] = MappingProxyType(
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
# Publisher-hierarchy nav ordering (root → volume), used for the
# membership / index checks in browser settings validation. A tuple of
# Collection members (collection-valued) so ``group in GROUP_ORDER`` and
# ``GROUP_ORDER.index(group)`` resolve against the engine's collection
# values (members compare equal to their value).
GROUP_ORDER = (
    Collection.ROOT,
    Collection.PUBLISHER,
    Collection.IMPRINT,
    Collection.SERIES,
    Collection.VOLUME,
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
            Collection.ROOT: None,
            Collection.PUBLISHER: Publisher,
            Collection.IMPRINT: Imprint,
            Collection.SERIES: Series,
            Collection.VOLUME: Volume,
            Collection.COMIC: Comic,
            Collection.FOLDER: Folder,
            Collection.ARC: StoryArc,
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
    {Collection.ROOT: Publisher, Collection.ARC: StoryArc, Collection.FOLDER: Folder}
)
EPOCH_START = datetime.fromtimestamp(0, tz=UTC)
ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
NONE_INTEGERFIELD = Value(None, PositiveSmallIntegerField())
NONE_DATETIMEFIELD = Value(None, DateTimeField())
EPOCH_START_DATETIMEFIELD = Value(EPOCH_START)
