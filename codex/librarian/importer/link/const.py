"""Link constants."""

from types import MappingProxyType

from codex.librarian.importer.const import (
    COMIC_FK_FIELDS,
    CREDIT_PERSON_FIELD_NAME,
    CREDIT_ROLE_FIELD_NAME,
    CREDITS_FIELD_NAME,
    IDENTIFIER_CODE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    NUMBER_FIELD_NAME,
    STORY_ARC_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
    UNIVERSES_FIELD_NAME,
)
from codex.models.named import Credit, Identifier, StoryArcNumber, Universe

DICT_MODEL_FIELD_NAME_CLASS_MAP = (
    (CREDITS_FIELD_NAME, Credit),
    (STORY_ARC_NUMBERS_FIELD_NAME, StoryArcNumber),
    (IDENTIFIERS_FIELD_NAME, Identifier),
    (UNIVERSES_FIELD_NAME, Universe),
)
DICT_MODEL_REL_LINK_MAP = MappingProxyType(
    {
        CREDITS_FIELD_NAME: (
            f"{CREDIT_PERSON_FIELD_NAME}__name",
            f"{CREDIT_ROLE_FIELD_NAME}__name",
        ),
        STORY_ARC_NUMBERS_FIELD_NAME: (
            f"{STORY_ARC_FIELD_NAME}__name",
            NUMBER_FIELD_NAME,
        ),
        IDENTIFIERS_FIELD_NAME: (
            f"{IDENTIFIER_TYPE_FIELD_NAME}__name",
            IDENTIFIER_CODE_FIELD_NAME,
        ),
        # TODO remove and use link_named_m2ms
        UNIVERSES_FIELD_NAME: (),
    }
)
COMIC_FK_FIELD_NAME_AND_MODEL = MappingProxyType(
    {
        field.name: field.related_model
        for field in COMIC_FK_FIELDS
        if field.related_model
    }
)
