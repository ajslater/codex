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
    BrowserCollectionModel,
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

# Collection constants sourced from the Collection enum. Each is a StrEnum
# member equal to its collection-name value, so existing
# ``collection == ROOT_COLLECTION`` checks are unaffected.
ROOT_COLLECTION = Collection.ROOT
FOLDER_COLLECTION = Collection.FOLDER
STORY_ARC_COLLECTION = Collection.ARC
COMIC_COLLECTION = Collection.COMIC
COLLECTION_NAME_MAP = MappingProxyType(
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
        **COLLECTION_NAME_MAP,
        FOLDER_COLLECTION: "folder",
        STORY_ARC_COLLECTION: "story-arc",
    }
)
MISSING_COVER_FN = "comic-165.webp"
MISSING_COVER_PATH = STATIC_IMG_PATH / MISSING_COVER_FN

# Annotated ``[str, str]`` (not ``[Collection, str]``): the keys are Collection members
# but lookups come in as their collection-value string (Collection is a StrEnum, so
# both resolve to the same bucket). The explicit annotation lets str-typed
# collection values index these maps without a type error.
COLLECTION_RELATION: MappingProxyType[str, str] = MappingProxyType(
    {
        **COLLECTION_NAME_MAP,
        COMIC_COLLECTION: "pk",
        FOLDER_COLLECTION: "parent_folder",
        STORY_ARC_COLLECTION: "story_arc_numbers__story_arc",
    }
)
FILTER_ONLY_COLLECTION_RELATION: MappingProxyType[str, str] = MappingProxyType(
    {
        **COLLECTION_RELATION,
        FOLDER_COLLECTION: "folders",
    }
)
METADATA_COLLECTION_RELATION = MappingProxyType(
    {
        **COLLECTION_NAME_MAP,
        COMIC_COLLECTION: "comic",
        FOLDER_COLLECTION: "comic__folders",
        STORY_ARC_COLLECTION: "comic__story_arc_numbers__story_arc",
    }
)
CUSTOM_COVER_COLLECTION_RELATION: MappingProxyType[str, str] = MappingProxyType(
    {
        **COLLECTION_NAME_MAP,
        FOLDER_COLLECTION: "folder",
        STORY_ARC_COLLECTION: "storyarc",
    }
)
# Publisher-hierarchy nav ordering (root → volume), used for the
# membership / index checks in browser settings validation. A tuple of
# Collection members (collection-valued) so ``collection in COLLECTION_ORDER``
# and ``COLLECTION_ORDER.index(collection)`` resolve against the engine's
# collection values (members compare equal to their value).
COLLECTION_ORDER = (
    Collection.ROOT,
    Collection.PUBLISHER,
    Collection.IMPRINT,
    Collection.SERIES,
    Collection.VOLUME,
)
MODEL_REL_MAP: MappingProxyType[type[BrowserCollectionModel], str] = MappingProxyType(
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
COLLECTION_MODEL_MAP: MappingProxyType[str, type[BrowserCollectionModel] | None] = (
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
COLLECTION_MODELS = (
    Publisher,
    Imprint,
    Series,
    Volume,
    Folder,
    StoryArc,
)
STATS_COLLECTION_MODELS = (
    *COLLECTION_MODELS,
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
COLLECTION_MTIME_MODEL_MAP = MappingProxyType(
    {Collection.ROOT: Publisher, Collection.ARC: StoryArc, Collection.FOLDER: Folder}
)
EPOCH_START = datetime.fromtimestamp(0, tz=UTC)
ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
NONE_INTEGERFIELD = Value(None, PositiveSmallIntegerField())
NONE_DATETIMEFIELD = Value(None, DateTimeField())
EPOCH_START_DATETIMEFIELD = Value(EPOCH_START)
