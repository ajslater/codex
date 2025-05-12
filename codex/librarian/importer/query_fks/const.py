"""Import query fks constants."""

from types import MappingProxyType

from codex.librarian.importer.const import (
    CONTRIBUTOR_PERSON_FIELD_NAME,
    CONTRIBUTOR_ROLE_FIELD_NAME,
    IDENTIFIER_CODE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIER_URL_FIELD_NAME,
    NUMBER_FIELD_NAME,
    STORY_ARC_FIELD_NAME,
)
from codex.models import (
    Contributor,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.models.named import (
    Identifier,
)

DICT_MODEL_REL_MAP = MappingProxyType(
    {
        Contributor: (
            f"{CONTRIBUTOR_PERSON_FIELD_NAME}__name",
            f"{CONTRIBUTOR_ROLE_FIELD_NAME}__name",
        ),
        StoryArcNumber: (
            f"{STORY_ARC_FIELD_NAME}__name",
            NUMBER_FIELD_NAME,
        ),
        Identifier: (
            f"{IDENTIFIER_TYPE_FIELD_NAME}__name",
            IDENTIFIER_CODE_FIELD_NAME,
            IDENTIFIER_URL_FIELD_NAME,
        ),
    }
)
GROUP_COMPARE_FIELDS: MappingProxyType[type[BrowserGroupModel], tuple[str, ...]] = (
    MappingProxyType(
        {
            Series: ("publisher__name", "imprint__name", "name"),
            Volume: ("publisher__name", "imprint__name", "series__name", "name"),
        }
    )
)
