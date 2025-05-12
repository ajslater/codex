"""Consts and maps for import."""

from types import MappingProxyType

from bidict import bidict
from comicbox.identifiers.const import NSS_KEY, URL_KEY
from comicbox.schemas.comicbox import (
    ARCS_KEY,
    CREDITS_KEY,
    IDENTIFIERS_KEY,
    NUMBER_KEY,
    ROLES_KEY,
)
from django.db.models import ForeignObjectRel
from django.db.models.fields import Field
from django.db.models.fields.related import ManyToManyField
from django.db.models.query_utils import DeferredAttribute

from codex.models import (
    Comic,
    Contributor,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.models.named import (
    ContributorPerson,
    ContributorRole,
    Identifier,
    IdentifierType,
)
from codex.models.paths import CustomCover

#################
# DICT METADATA #
#################
CONTRIBUTORS_FIELD_NAME = "contributors"
_CONTRIBUTOR_PERSON_FIELD_NAME = "person"
_CONTRIBUTOR_ROLE_FIELD_NAME = "role"
STORY_ARCS_METADATA_KEY = "story_arcs"
STORY_ARC_NUMBERS_FK_NAME = "story_arc_numbers"
_STORY_ARC_NUMBER_FK_NAME = "story_arc_number"
STORY_ARC_FIELD_NAME = "story_arc"
_NUMBER_FIELD_NAME = "number"
IDENTIFIERS_FIELD_NAME = "identifiers"
_IDENTIFIER_TYPE_FIELD_NAME = "identifier_type"
_IDENTIFIER_CODE_FIELD_NAME = "nss"
_IDENTIFIER_URL_FIELD_NAME = "url"

# AGGREGATE
FIELD_NAME_TO_MD_KEY_MAP = MappingProxyType(
    {STORY_ARC_NUMBERS_FK_NAME: ARCS_KEY, CONTRIBUTORS_FIELD_NAME: CREDITS_KEY}
)
DICT_MODEL_AGG_MAP: MappingProxyType[str, dict[str, DeferredAttribute]] = (  # pyright: ignore[reportAssignmentType]
    MappingProxyType(
        {
            CONTRIBUTORS_FIELD_NAME: {ROLES_KEY: ContributorRole.name},
            IDENTIFIERS_FIELD_NAME: {NSS_KEY: Identifier.nss, URL_KEY: Identifier.url},
            STORY_ARC_NUMBERS_FK_NAME: {NUMBER_KEY: StoryArcNumber.number},
        }
    )
)
DICT_MODEL_SUB_FIELDS = MappingProxyType(
    {
        CREDITS_KEY: ContributorPerson,
        ROLES_KEY: ContributorRole,
        IDENTIFIERS_KEY: IdentifierType,
        ARCS_KEY: StoryArc,
    }
)
DICT_MODEL_FOR_VALUE = MappingProxyType(
    {
        ARCS_KEY: StoryArcNumber,
        CREDITS_KEY: Contributor,
        IDENTIFIERS_KEY: IdentifierType,
    }
)

## QUERY
DICT_MODEL_FIELD_MODEL_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: Contributor,
        STORY_ARCS_METADATA_KEY: StoryArcNumber,
        IDENTIFIERS_FIELD_NAME: Identifier,
    }
)
DICT_MODEL_REL_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: (
            f"{_CONTRIBUTOR_ROLE_FIELD_NAME}__name",
            f"{_CONTRIBUTOR_PERSON_FIELD_NAME}__name",
        ),
        STORY_ARCS_METADATA_KEY: (
            f"{STORY_ARC_FIELD_NAME}__name",
            _NUMBER_FIELD_NAME,
        ),
        IDENTIFIERS_FIELD_NAME: (
            f"{_IDENTIFIER_TYPE_FIELD_NAME}__name",
            {
                "nss": _IDENTIFIER_CODE_FIELD_NAME,
            },
        ),
    }
)
# CREATE
CREATE_DICT_UPDATE_FIELDS = MappingProxyType(
    {
        Contributor: (_CONTRIBUTOR_ROLE_FIELD_NAME, _CONTRIBUTOR_PERSON_FIELD_NAME),
        StoryArcNumber: (STORY_ARC_FIELD_NAME, _NUMBER_FIELD_NAME),
        Identifier: (_IDENTIFIER_TYPE_FIELD_NAME, _IDENTIFIER_CODE_FIELD_NAME),
    }
)
# LINK
DICT_MODEL_FIELD_NAME_CLASS_MAP = (
    (CONTRIBUTORS_FIELD_NAME, Contributor),
    (STORY_ARCS_METADATA_KEY, StoryArcNumber),
    (IDENTIFIERS_FIELD_NAME, Identifier),
)
DICT_MODEL_REL_LINK_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: (
            f"{_CONTRIBUTOR_ROLE_FIELD_NAME}__name",
            f"{_CONTRIBUTOR_PERSON_FIELD_NAME}__name__in",
        ),
        STORY_ARC_NUMBERS_FK_NAME: (
            f"{STORY_ARC_FIELD_NAME}__name",
            _NUMBER_FIELD_NAME,
        ),
        IDENTIFIERS_FIELD_NAME: (
            f"{_IDENTIFIER_TYPE_FIELD_NAME}__name",
            _IDENTIFIER_CODE_FIELD_NAME,
        ),
    }
)


###############
# BULK UPDATE #
###############

_EXCLUDEBULK_UPDATE_COMIC_FIELDS = {
    "bookmark",
    "created_at",
    "id",
    "library",
    "comicfts",
}
GROUP_BASE_FIELDS = ("name", "sort_name")
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
    *GROUP_BASE_FIELDS,
    "stat",
    "updated_at",
    "path",
    "parent_folder",
)
BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
BULK_UPDATE_COMIC_FIELDS_WITH_VALUES = tuple(
    sorted(
        frozenset(BULK_UPDATE_COMIC_FIELDS)
        - frozenset(BULK_UPDATE_FOLDER_MODIFIED_FIELDS)
    )
)
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder", "stat", "updated_at")
MOVED_BULK_FOLDER_UPDATE_FIELDS = (
    "path",
    "parent_folder",
    *GROUP_BASE_FIELDS,
    "stat",
    "updated_at",
)
CUSTOM_COVER_UPDATE_FIELDS = ("path", "stat", "updated_at", "sort_name", "group")

#########
# OTHER #
#########
VOLUME_COUNT = "volume_count"
ISSUE_COUNT = "issue_count"
COUNT_FIELDS: MappingProxyType[type[BrowserGroupModel], str | None] = MappingProxyType(
    {Publisher: None, Imprint: None, Series: VOLUME_COUNT, Volume: ISSUE_COUNT}
)
_GROUP_CLASSES = (Publisher, Imprint, Series, Volume)


def _create_group_update_fields():
    guf = {}
    fields = GROUP_BASE_FIELDS
    for cls in _GROUP_CLASSES:
        if cls == Volume:
            guf[cls] = tuple({*fields} - {"sort_name"})
        else:
            guf[cls] = fields
        fields = (*fields, cls.__name__.lower())
    return MappingProxyType(guf)


GROUP_UPDATE_FIELDS = _create_group_update_fields()
NAMED_MODEL_UPDATE_FIELDS = ("name",)
FOLDERS_FIELD = "folders"
GROUP_TREES = "group_trees"
COMIC_PATHS = "comic_paths"
PUBLISHER = "publisher"
IMPRINT = "imprint"
VOLUME = "volume"
SERIES = "series"
PARENT_FOLDER = "parent_folder"
COMIC_VALUES = "comic_values"
M2M_LINK = "m2m_link"
FK_LINK = "fk_link"
QUERY_MODELS = "query_models"
FIS = "fis"
FK_CREATE = "fk_create"
COVERS_UPDATE = "covers_update"
COVERS_CREATE = "covers_create"
LINK_COVER_PKS = "link_cover_pks"
GROUP_COMPARE_FIELDS: MappingProxyType[type[BrowserGroupModel], tuple[str, ...]] = (
    MappingProxyType(
        {
            Series: ("publisher__name", "imprint__name", "name"),
            Volume: ("publisher__name", "imprint__name", "series__name", "name"),
        }
    )
)
CLASS_CUSTOM_COVER_GROUP_MAP = bidict(
    {
        Publisher: CustomCover.GroupChoice.P.value,
        Imprint: CustomCover.GroupChoice.I.value,
        Series: CustomCover.GroupChoice.S.value,
        StoryArc: CustomCover.GroupChoice.A.value,
        Folder: CustomCover.GroupChoice.F.value,
    }
)

_COMIC_FK_FIELDS: tuple[Field | ForeignObjectRel, ...] = tuple(
    field
    for field in Comic._meta.get_fields()
    if field
    and field.many_to_one
    and field.name != "library"
    and field.related_model
    and not issubclass(field.related_model, BrowserGroupModel)
)

COMIC_FK_FIELD_NAMES: MappingProxyType[str, Field] = MappingProxyType(
    {
        field.name: field.related_model._meta.get_field("name")
        for field in _COMIC_FK_FIELDS
        if field.related_model
    }
)
COMIC_FK_FIELD_NAME_AND_MODEL = MappingProxyType(
    {
        field.name: field.related_model
        for field in _COMIC_FK_FIELDS
        if field.related_model
    }
)
COMIC_M2M_FIELD_NAMES: tuple[ManyToManyField, ...] = (  # pyright: ignore[reportAssignmentType]
    # Leaves out folders.
    field
    for field in Comic._meta.get_fields()
    if field.many_to_many and field.name != "folders"
)
COMIC_GROUP_FIELD_NAMES = (
    "publisher",
    "imprint",
    "series",
    "volume",
    "story_arc_numbers",
    "folders",
)

FKC_CONTRIBUTORS = "create_contributors"
FKC_STORY_ARC_NUMBERS = "create_story_arc_numbers"
FKC_IDENTIFIERS = "create_identifiers"
FKC_CREATE_GROUPS = "create_groups"
FKC_UPDATE_GROUPS = "update_groups"
FKC_CREATE_FKS = "create_fks"
FKC_FOLDER_PATHS = "create_folder_paths"
FKC_TOTAL_FKS = "total_fks"
