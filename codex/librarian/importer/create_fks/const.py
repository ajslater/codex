"""Create fks consts."""

from types import MappingProxyType

from codex.librarian.importer.const import (
    CREDIT_PERSON_FIELD_NAME,
    CREDIT_ROLE_FIELD_NAME,
    DESIGNATION_FIELD_NAME,
    GROUP_MODEL_COUNT_FIELDS,
    IDENTIFIER_CODE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIER_URL_FIELD_NAME,
    NAME_FIELD_NAME,
    NUMBER_FIELD_NAME,
    STORY_ARC_FIELD_NAME,
)
from codex.models import (
    Credit,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.named import (
    CreditPerson,
    CreditRole,
    Identifier,
    IdentifierType,
    Universe,
)

GROUP_BASE_FIELDS = ("name", "sort_name")
CREATE_DICT_UPDATE_FIELDS = MappingProxyType(
    {
        Credit: (CREDIT_ROLE_FIELD_NAME, CREDIT_PERSON_FIELD_NAME),
        Identifier: (IDENTIFIER_TYPE_FIELD_NAME, IDENTIFIER_CODE_FIELD_NAME),
        StoryArcNumber: (STORY_ARC_FIELD_NAME, NUMBER_FIELD_NAME),
        Universe: (DESIGNATION_FIELD_NAME,),
    }
)
CREATE_DICT_FUNCTION_ARGS = MappingProxyType(
    {
        Credit: {
            CREDIT_PERSON_FIELD_NAME: CreditPerson,
            CREDIT_ROLE_FIELD_NAME: CreditRole,
        },
        Identifier: {
            IDENTIFIER_TYPE_FIELD_NAME: IdentifierType,
            IDENTIFIER_CODE_FIELD_NAME: None,
            IDENTIFIER_URL_FIELD_NAME: None,
        },
        StoryArcNumber: {STORY_ARC_FIELD_NAME: StoryArc, NUMBER_FIELD_NAME: None},
        Universe: {NAME_FIELD_NAME: None, DESIGNATION_FIELD_NAME: None},
    }
)


def _create_group_update_fields():
    guf = {}
    fields = GROUP_BASE_FIELDS
    for cls in GROUP_MODEL_COUNT_FIELDS:
        if cls == Volume:
            guf[cls] = tuple({*fields} - {"sort_name"})
        else:
            guf[cls] = fields
        fields = (*fields, cls.__name__.lower())
    return MappingProxyType(guf)


GROUP_UPDATE_FIELDS = _create_group_update_fields()
NAMED_MODEL_UPDATE_FIELDS = ("name",)
