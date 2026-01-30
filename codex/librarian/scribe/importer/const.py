"""Consts and maps for import."""

from types import MappingProxyType, SimpleNamespace

from bidict import frozenbidict
from django.db.models.fields import Field
from django.db.models.fields.related import ForeignObjectRel, ManyToManyField

from codex.models.base import BaseModel
from codex.models.comic import Comic
from codex.models.groups import (
    BrowserGroupModel,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.models.identifier import Identifier, IdentifierSource
from codex.models.named import (
    AgeRating,
    Character,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Genre,
    Language,
    Location,
    OriginalFormat,
    ScanInfo,
    SeriesGroup,
    Story,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
    Universe,
)
from codex.models.paths import CustomCover

###############
# FIELD NAMES #
###############
FOLDERS_FIELD_NAME = "folders"
PUBLISHER_FIELD_NAME = "publisher"
IMPRINT_FIELD_NAME = "imprint"
VOLUME_FIELD_NAME = "volume"
SERIES_FIELD_NAME = "series"
PARENT_FOLDER_FIELD_NAME = "parent_folder"
VOLUME_COUNT_FIELD_NAME = "volume_count"
ISSUE_COUNT_FIELD_NAME = "issue_count"
PATH_FIELD_NAME = "path"
IDENTIFIERS_FIELD_NAME = "identifiers"
NON_FTS_FIELDS = frozenset(
    {
        # Attributes
        "critical_rating",
        "day",
        "file_type",
        "issue_number",
        "issue_suffix",
        "metadata_mtime",
        "monochrome",
        "month",
        "notes",
        "page_count",
        "path",
        "reading_direction",
        "year",
        # FKs
        PARENT_FOLDER_FIELD_NAME,
        VOLUME_FIELD_NAME,
        # M2Ms
        FOLDERS_FIELD_NAME,
        IDENTIFIERS_FIELD_NAME,
    }
)

##########################
# IMPORTER METADATA KEYS #
##########################
EXTRACTED = "extracted"
SKIPPED = "skipped"
QUERY_MODELS = "query_models"
CREATE_COMICS = "create_comics"
CREATE_FKS = "create_fks"
CREATE_COVERS = "create_covers"
UPDATE_COMICS = "update_comics"
UPDATE_FKS = "update_fks"
UPDATE_COVERS = "update_covers"
LINK_COVER_PKS = "link_cover_pks"
LINK_FKS = "link_fks"
LINK_M2MS = "link_m2ms"
DELETE_M2MS = "delete_m2ms"
FIS = "fis"
TOTAL = "total"
FK_KEYS = SimpleNamespace(CREATE_FKS=CREATE_FKS, UPDATE_FKS=UPDATE_FKS)
FTS_UPDATE = "fts_update"
FTS_CREATE = "fts_create"
FTS_EXISTING_M2MS = "fts_existing_m2ms"
FTS_CREATED_M2MS = "fts_created_m2ms"
FTS_UPDATED_M2MS = "fts_updated_m2ms"

#######
# M2M #
#######
GROUP_MODEL_COUNT_FIELDS: MappingProxyType[type[BrowserGroupModel], str | None] = (
    MappingProxyType(
        {
            Publisher: None,
            Imprint: None,
            Series: VOLUME_COUNT_FIELD_NAME,
            Volume: ISSUE_COUNT_FIELD_NAME,
        }
    )
)
COMIC_M2M_FIELDS: tuple[ManyToManyField, ...] = tuple(  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
    field for field in Comic._meta.get_fields() if field.many_to_many
)
COMIC_M2M_FIELD_NAMES: tuple[str, ...] = tuple(field.name for field in COMIC_M2M_FIELDS)
COMPLEX_M2M_MODELS = (Credit, Identifier, StoryArcNumber)

########################
# COMPLEX M2M METADATA #
########################
DictModelType = Credit | Identifier | StoryArcNumber
CREDITS_FIELD_NAME = "credits"
CREDIT_PERSON_FIELD_NAME = "person"
CREDIT_ROLE_FIELD_NAME = "role"
STORY_ARC_NUMBERS_FIELD_NAME = "story_arc_numbers"
STORY_ARC_FIELD_NAME = "story_arc"
NUMBER_FIELD_NAME = "number"
IDENTIFIER_SOURCE_FIELD_NAME = "source"
IDENTIFIER_TYPE_FIELD_NAME = "id_type"
IDENTIFIER_ID_KEY_FIELD_NAME = "key"
IDENTIFIER_URL_FIELD_NAME = "url"
UNIVERSES_FIELD_NAME = "universes"
NAME_FIELD_NAME = "name"
NUMBER_TO_FIELD_NAME = "number_to"
IDENTIFIER_FIELD_NAME = "identifier"
DESIGNATION_FIELD_NAME = "designation"

########################
# QUERY AND CREATE FKS #
########################
COMIC_FK_FIELDS: tuple[Field | ForeignObjectRel, ...] = tuple(
    field
    for field in Comic._meta.get_fields()
    if field
    and field.many_to_one
    and field.name != "library"
    and field.related_model
    and not issubclass(field.related_model, BrowserGroupModel)
)
GROUP_FIELD_NAMES = ("publisher", "imprint", "series", "volume")
GROUP_FIELD_NAMES_SET = frozenset(GROUP_FIELD_NAMES)
_COMIC_GROUP_FIELDS: tuple[Field, ...] = tuple(
    Comic._meta.get_field(field_name) for field_name in GROUP_FIELD_NAMES
)
ALL_COMIC_FK_FIELDS = (*_COMIC_GROUP_FIELDS, *COMIC_FK_FIELDS)
COMIC_FK_FIELD_NAMES: tuple[str, ...] = tuple(
    field.name for field in ALL_COMIC_FK_FIELDS
)
PROTAGONIST_FIELD_MODEL_MAP = MappingProxyType(
    {"main_character": Character, "main_team": Team}
)
_DEFAULT_KEY_INDEX = 1
_IDENTIFIER_RELS = (
    "identifier__source__name",
    "identifier__id_type",
    "identifier__key",
)
_NAMED_MODEL_RELS = ((NAME_FIELD_NAME,), "")
NAMED_MODELS = frozenset(
    {
        AgeRating,
        Country,
        Language,
        OriginalFormat,
        Tagger,
        ScanInfo,
        SeriesGroup,
        IdentifierSource,
    }
)
_IDENTIFIED_MODEL_RELS = ((NAME_FIELD_NAME,), _IDENTIFIER_RELS)
IDENTIFIED_MODELS = frozenset(
    {Character, CreditPerson, CreditRole, Genre, Location, Story, StoryArc, Tag, Team}
)
MODEL_REL_MAP: MappingProxyType[type[BaseModel], tuple[str | tuple[str, ...], ...]] = (
    MappingProxyType(
        {
            **dict.fromkeys(NAMED_MODELS, _NAMED_MODEL_RELS),
            **dict.fromkeys(IDENTIFIED_MODELS, _IDENTIFIED_MODEL_RELS),
            Identifier: (
                (
                    f"{IDENTIFIER_SOURCE_FIELD_NAME}__name",
                    IDENTIFIER_TYPE_FIELD_NAME,
                    IDENTIFIER_ID_KEY_FIELD_NAME,
                ),
                "",
                IDENTIFIER_URL_FIELD_NAME,
            ),
            Publisher: _IDENTIFIED_MODEL_RELS,
            Imprint: (
                (
                    "publisher__name",
                    NAME_FIELD_NAME,
                ),
                _IDENTIFIER_RELS,
            ),
            Series: (
                (
                    "publisher__name",
                    "imprint__name",
                    NAME_FIELD_NAME,
                ),
                _IDENTIFIER_RELS,
                VOLUME_COUNT_FIELD_NAME,
            ),
            Volume: (
                (
                    "publisher__name",
                    "imprint__name",
                    "series__name",
                    NAME_FIELD_NAME,
                    NUMBER_TO_FIELD_NAME,
                ),
                "",
                ISSUE_COUNT_FIELD_NAME,
            ),
            Folder: (
                (PATH_FIELD_NAME,),
                "",
            ),
            Credit: (
                (
                    f"{CREDIT_PERSON_FIELD_NAME}__name",
                    f"{CREDIT_ROLE_FIELD_NAME}__name",
                ),
                "",
            ),
            StoryArcNumber: (
                (f"{STORY_ARC_FIELD_NAME}__name", NUMBER_FIELD_NAME),
                "",
            ),
            Universe: ((NAME_FIELD_NAME,), _IDENTIFIER_RELS, DESIGNATION_FIELD_NAME),
        }
    )
)
_IDENTIFIED_SELECT_RELATED = ("identifier", "identifier__source")
MODEL_SELECT_RELATED: MappingProxyType[type[BaseModel], tuple[str, ...]] = (
    MappingProxyType(
        {
            **dict.fromkeys(IDENTIFIED_MODELS, _IDENTIFIED_SELECT_RELATED),
            Identifier: (IDENTIFIER_SOURCE_FIELD_NAME,),
            Publisher: _IDENTIFIED_SELECT_RELATED,
            Imprint: ("publisher",),
            Series: ("publisher", "imprint"),
            Volume: ("publisher", "imprint", "series"),
            Credit: (CREDIT_PERSON_FIELD_NAME, CREDIT_ROLE_FIELD_NAME),
            StoryArcNumber: (STORY_ARC_FIELD_NAME,),
            Universe: _IDENTIFIED_SELECT_RELATED,
        }
    )
)
FIELD_NAME_KEYS_REL_MAP = MappingProxyType(
    {
        field.name: MODEL_REL_MAP[field.related_model][0]  # pyright: ignore[reportArgumentType]
        for field in (*ALL_COMIC_FK_FIELDS, *COMIC_M2M_FIELDS)
    }
)
_NAMED_MODEL_ATTRS = ("name",)
_IDENTIFIER_KEY_ATTRS = (
    IDENTIFIER_SOURCE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIER_ID_KEY_FIELD_NAME,
)
FIELD_NAME_KEY_ATTRS_MAP = MappingProxyType(
    {
        **dict.fromkeys(COMIC_M2M_FIELD_NAMES, _NAMED_MODEL_ATTRS),
        FOLDERS_FIELD_NAME: ("path",),
        IDENTIFIER_FIELD_NAME: _IDENTIFIER_KEY_ATTRS,
        IDENTIFIERS_FIELD_NAME: _IDENTIFIER_KEY_ATTRS,
        PUBLISHER_FIELD_NAME: _NAMED_MODEL_ATTRS,
        IMPRINT_FIELD_NAME: (PUBLISHER_FIELD_NAME, *_NAMED_MODEL_ATTRS),
        SERIES_FIELD_NAME: (
            PUBLISHER_FIELD_NAME,
            IMPRINT_FIELD_NAME,
            *_NAMED_MODEL_ATTRS,
        ),
        VOLUME_FIELD_NAME: (
            PUBLISHER_FIELD_NAME,
            IMPRINT_FIELD_NAME,
            SERIES_FIELD_NAME,
            *_NAMED_MODEL_ATTRS,
        ),
        CREDITS_FIELD_NAME: (CREDIT_PERSON_FIELD_NAME, CREDIT_ROLE_FIELD_NAME),
        STORY_ARC_NUMBERS_FIELD_NAME: (STORY_ARC_FIELD_NAME, NUMBER_FIELD_NAME),
    }
)


def get_key_index(model: type[BaseModel]) -> int:
    """Return the key index divider for a model tuple."""
    return len(MODEL_REL_MAP[model][0])


#################
# CREATE COMICS #
#################
_EXCLUDEBULK_UPDATE_COMIC_FIELDS = {
    "bookmark",
    "created_at",
    "id",
    "library",
    "comicfts",
}
BULK_UPDATE_COMIC_FIELDS = tuple(
    sorted(
        field.name
        for field in Comic._meta.get_fields()
        if (not field.many_to_many)
        and (field.name not in _EXCLUDEBULK_UPDATE_COMIC_FIELDS)
    )
)
BULK_CREATE_COMIC_FIELDS = (*BULK_UPDATE_COMIC_FIELDS, "library")
BULK_UPDATE_FOLDER_FIELDS = (
    "name",
    "parent_folder",
    "path",
    "sort_name",
    "stat",
    "updated_at",
)
BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")

##########
# COVERS #
##########
CLASS_CUSTOM_COVER_GROUP_MAP = frozenbidict(
    {
        Publisher: CustomCover.GroupChoices.P.value,
        Imprint: CustomCover.GroupChoices.I.value,
        Series: CustomCover.GroupChoices.S.value,
        StoryArc: CustomCover.GroupChoices.A.value,
        Folder: CustomCover.GroupChoices.F.value,
    }
)

#########
# MOVED #
#########
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder", "stat", "updated_at")
CUSTOM_COVER_UPDATE_FIELDS = ("path", "stat", "updated_at", "sort_name", "group")

###########
# DELETED #
###########
ALL_COMIC_GROUP_FIELD_NAMES = (
    *GROUP_FIELD_NAMES,
    "story_arc_numbers",
    "folders",
)

##########
# Failed #
##########
UPDATE_FIS = "update_fis"
CREATE_FIS = "create_fis"
DELETE_FI_PATHS = "delete_fi_paths"
BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")
