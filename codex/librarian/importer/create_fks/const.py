"""Create fks consts."""

from types import MappingProxyType

from codex.librarian.importer.const import (
    CREDIT_PERSON_FIELD_NAME,
    CREDIT_ROLE_FIELD_NAME,
    FKC_CREDITS,
    FKC_IDENTIFIERS,
    FKC_STORY_ARC_NUMBERS,
    GROUP_MODEL_COUNT_FIELDS,
    IDENTIFIER_CODE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
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
)

GROUP_BASE_FIELDS = ("name", "sort_name")
CREATE_DICT_UPDATE_FIELDS = MappingProxyType(
    {
        Credit: (CREDIT_ROLE_FIELD_NAME, CREDIT_PERSON_FIELD_NAME),
        StoryArcNumber: (STORY_ARC_FIELD_NAME, NUMBER_FIELD_NAME),
        Identifier: (IDENTIFIER_TYPE_FIELD_NAME, IDENTIFIER_CODE_FIELD_NAME),
    }
)
CREATE_DICT_FUNCTION_ARGS = (
    (
        Credit,
        FKC_CREDITS,
        {"person": CreditPerson, "role": CreditRole},
    ),
    (StoryArcNumber, FKC_STORY_ARC_NUMBERS, {"story_arc": StoryArc}),
    (
        Identifier,
        FKC_IDENTIFIERS,
        {"identifier_type": IdentifierType, "nss": None, "url": None},
    ),
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
