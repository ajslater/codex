"""Consts and maps for import."""

from types import MappingProxyType

from bidict import bidict
from django.db.models.fields import Field
from django.db.models.fields.related import ForeignObjectRel, ManyToManyField

from codex.models import (
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.models.named import Contributor, Identifier, StoryArcNumber
from codex.models.paths import CustomCover

###############
# FIELD NAMES #
###############
FOLDERS_FIELD = "folders"
PUBLISHER = "publisher"
IMPRINT = "imprint"
VOLUME = "volume"
SERIES = "series"
PARENT_FOLDER = "parent_folder"
VOLUME_COUNT = "volume_count"
ISSUE_COUNT = "issue_count"

##########################
# IMPORTER METADATA KEYS #
##########################
COMIC_PATHS = "comic_paths"
COMIC_VALUES = "comic_values"
M2M_LINK = "m2m_link"
FK_LINK = "fk_link"
QUERY_MODELS = "query_models"
FIS = "fis"
FK_CREATE = "fk_create"
COVERS_UPDATE = "covers_update"
COVERS_CREATE = "covers_create"
LINK_COVER_PKS = "link_cover_pks"
FKC_CONTRIBUTORS = "create_contributors"
FKC_STORY_ARC_NUMBERS = "create_story_arc_numbers"
FKC_IDENTIFIERS = "create_identifiers"
FKC_CREATE_GROUPS = "create_groups"
FKC_UPDATE_GROUPS = "update_groups"
FKC_CREATE_FKS = "create_fks"
FKC_FOLDER_PATHS = "create_folder_paths"
FKC_TOTAL_FKS = "total_fks"


#######
# M2M #
#######
GROUP_MODEL_COUNT_FIELDS: MappingProxyType[type[BrowserGroupModel], str | None] = (
    MappingProxyType(
        {Publisher: None, Imprint: None, Series: VOLUME_COUNT, Volume: ISSUE_COUNT}
    )
)
COMIC_M2M_FIELDS: tuple[ManyToManyField, ...] = (  # pyright: ignore[reportAssignmentType]
    # Leaves out folders.
    field
    for field in Comic._meta.get_fields()
    if field.many_to_many and field.name != "folders"
)


#################
# DICT METADATA #
#################
DictModelType = type[Contributor] | type[StoryArcNumber] | type[Identifier]
CONTRIBUTORS_FIELD_NAME = "contributors"
CONTRIBUTOR_PERSON_FIELD_NAME = "person"
CONTRIBUTOR_ROLE_FIELD_NAME = "role"
STORY_ARC_NUMBERS_FIELD_NAME = "story_arc_numbers"
_STORY_ARC_NUMBER_FK_NAME = "story_arc_number"
STORY_ARC_FIELD_NAME = "story_arc"
NUMBER_FIELD_NAME = "number"
IDENTIFIERS_FIELD_NAME = "identifiers"
IDENTIFIER_TYPE_FIELD_NAME = "identifier_type"
IDENTIFIER_CODE_FIELD_NAME = "nss"
IDENTIFIER_URL_FIELD_NAME = "url"

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
BULK_UPDATE_COMIC_FIELDS_WITH_VALUES = tuple(
    sorted(
        frozenset(BULK_UPDATE_COMIC_FIELDS)
        - frozenset(BULK_UPDATE_FOLDER_MODIFIED_FIELDS)
    )
)

##########
# COVERS #
##########
CLASS_CUSTOM_COVER_GROUP_MAP = bidict(
    {
        Publisher: CustomCover.GroupChoice.P.value,
        Imprint: CustomCover.GroupChoice.I.value,
        Series: CustomCover.GroupChoice.S.value,
        StoryArc: CustomCover.GroupChoice.A.value,
        Folder: CustomCover.GroupChoice.F.value,
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
COMIC_GROUP_FIELD_NAMES = (
    "publisher",
    "imprint",
    "series",
    "volume",
    "story_arc_numbers",
    "folders",
)
