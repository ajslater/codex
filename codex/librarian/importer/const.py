"""Consts and maps for import."""

from types import MappingProxyType

from codex.models import (
    Comic,
    Contributor,
    Imprint,
    Publisher,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.models.named import Identifier

#################
# DICT METADATA #
#################
CONTRIBUTORS_FIELD_NAME = "contributors"
_CONTRIBUTOR_PERSON_FIELD_NAME = "person"
_CONTRIBUTOR_ROLE_FIELD_NAME = "role"
STORY_ARCS_METADATA_KEY = "story_arcs"
STORY_ARC_NUMBERS_FK_NAME = "story_arc_numbers"
_STORY_ARC_FIELD_NAME = "story_arc"
_NUMBER_FIELD_NAME = "number"
IDENTIFIERS_FIELD_NAME = "identifiers"
_IDENTIFIER_TYPE_FIELD_NAME = "identifier_type"
_IDENTIFIER_CODE_FIELD_NAME = "nss"
_IDENTIFIER_URL_FIELD_NAME = "url"

# AGGREGATE
DICT_MODEL_AGG_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: (
            _CONTRIBUTOR_ROLE_FIELD_NAME,
            _CONTRIBUTOR_PERSON_FIELD_NAME,
        ),
        STORY_ARCS_METADATA_KEY: (_STORY_ARC_FIELD_NAME, None),
        IDENTIFIERS_FIELD_NAME: (_IDENTIFIER_TYPE_FIELD_NAME, None),
    }
)
## QUERY
DICT_MODEL_CLASS_FIELDS_MAP = MappingProxyType(
    {
        Contributor: frozenset(
            {_CONTRIBUTOR_ROLE_FIELD_NAME, _CONTRIBUTOR_PERSON_FIELD_NAME}
        ),
        StoryArcNumber: frozenset({_STORY_ARC_FIELD_NAME}),
        Identifier: frozenset({_IDENTIFIER_TYPE_FIELD_NAME}),
    }
)
DICT_MODEL_REL_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: (
            Contributor,
            f"{_CONTRIBUTOR_ROLE_FIELD_NAME}__name",
            f"{_CONTRIBUTOR_PERSON_FIELD_NAME}__name",
        ),
        STORY_ARCS_METADATA_KEY: (
            StoryArcNumber,
            f"{_STORY_ARC_FIELD_NAME}__name",
            _NUMBER_FIELD_NAME,
        ),
    }
)
IDENTIFIERS_MODEL_REL_MAP = MappingProxyType(
    {
        IDENTIFIERS_FIELD_NAME: (
            Identifier,
            f"{_IDENTIFIER_TYPE_FIELD_NAME}__name",
            {
                "nss": _IDENTIFIER_CODE_FIELD_NAME,
                "url": _IDENTIFIER_URL_FIELD_NAME,
            },
        ),
    }
)
# CREATE
CREATE_DICT_UPDATE_FIELDS = MappingProxyType(
    {
        Contributor: (_CONTRIBUTOR_ROLE_FIELD_NAME, _CONTRIBUTOR_PERSON_FIELD_NAME),
        StoryArcNumber: (_STORY_ARC_FIELD_NAME, _NUMBER_FIELD_NAME),
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
            f"{_STORY_ARC_FIELD_NAME}__name",
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
    "created_at",
    "searchresult",
    "id",
    "bookmark",
}
BULK_UPDATE_COMIC_FIELDS = tuple(
    sorted(
        field.name
        for field in Comic._meta.get_fields()
        if (not field.many_to_many)
        and (field.name not in _EXCLUDEBULK_UPDATE_COMIC_FIELDS)
    )
)
BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
BULK_UPDATE_COMIC_FIELDS_WITH_VALUES = tuple(
    sorted(
        frozenset(BULK_UPDATE_COMIC_FIELDS)
        - frozenset(BULK_UPDATE_FOLDER_MODIFIED_FIELDS)
    )
)

#########
# OTHER #
#########
VOLUME_COUNT = "volume_count"
ISSUE_COUNT = "issue_count"
COUNT_FIELDS = {Series: VOLUME_COUNT, Volume: ISSUE_COUNT}
GROUP_UPDATE_FIELDS = MappingProxyType(
    {
        Publisher: ("name",),
        Imprint: ("name", "publisher"),
        Series: ("name", "imprint"),
        Volume: ("name", "publisher", "imprint", "series"),
    }
)
NAMED_MODEL_UPDATE_FIELDS = ("name",)
FOLDERS_FIELD = "folders"
GROUP_TREES = "group_trees"
COMIC_PATHS = "comic_paths"
PUBLISHER = "publisher"
IMPRINT = "imprint"
VOLUME = "volume"
SERIES = "series"
PARENT_FOLDER = "parent_folder"
MDS = "mds"
M2M_MDS = "m2m_mds"
FKS = "fks"
FIS = "fis"
GROUP_COMPARE_FIELDS = MappingProxyType(
    {
        Series: ("publisher__name", "imprint__name", "name"),
        Volume: ("publisher__name", "imprint__name", "series__name", "name"),
    }
)

COMIC_FK_FIELD_NAMES = frozenset(
    field.name
    for field in Comic._meta.get_fields()
    if field.many_to_one
    and field.name != "library"
    and field.related_model
    and not issubclass(field.related_model, BrowserGroupModel)
)
COMIC_M2M_FIELD_NAMES = frozenset(
    # Leaves out folders.
    field.name
    for field in Comic._meta.get_fields()
    if field.many_to_many and field.name != "folders"
)
