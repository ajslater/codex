"""Import query fks constants."""

from types import MappingProxyType

from codex.librarian.importer.const import (
    CREDIT_PERSON_FIELD_NAME,
    CREDIT_ROLE_FIELD_NAME,
    DESIGNATION_FIELD_NAME,
    IDENTIFIER_CODE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIER_URL_FIELD_NAME,
    NAME_FIELD_NAME,
    NUMBER_FIELD_NAME,
    STORY_ARC_FIELD_NAME,
    DictModelType,
)
from codex.models import (
    Credit,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.models.named import (
    Identifier,
    Universe,
)

COMPLEX_M2M_MODEL_REL_MAP: MappingProxyType[DictModelType, tuple[str, ...]] = (
    MappingProxyType(
        {
            Credit: (
                f"{CREDIT_PERSON_FIELD_NAME}__name",
                f"{CREDIT_ROLE_FIELD_NAME}__name",
            ),
            Identifier: (
                f"{IDENTIFIER_TYPE_FIELD_NAME}__name",
                IDENTIFIER_CODE_FIELD_NAME,
                IDENTIFIER_URL_FIELD_NAME,
            ),
            StoryArcNumber: (
                f"{STORY_ARC_FIELD_NAME}__name",
                NUMBER_FIELD_NAME,
            ),
            Universe: (
                NAME_FIELD_NAME,
                DESIGNATION_FIELD_NAME,
            ),
        }
    )
)
GROUP_COMPARE_FIELDS: MappingProxyType[type[BrowserGroupModel], tuple[str, ...]] = (
    MappingProxyType(
        {
            Series: ("publisher__name", "imprint__name", "name"),
            Volume: ("publisher__name", "imprint__name", "series__name", "name"),
        }
    )
)
