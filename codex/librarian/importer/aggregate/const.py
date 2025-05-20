"""Aggregate Consts."""

from types import MappingProxyType

from comicbox.identifiers.const import NSS_KEY, URL_KEY
from comicbox.schemas.comicbox import (
    ARCS_KEY,
    DESIGNATION_KEY,
    NUMBER_KEY,
    PROTAGONIST_KEY,
    ROLES_KEY,
)
from django.db.models.fields import Field
from django.db.models.query_utils import DeferredAttribute

from codex.librarian.importer.const import (
    COMIC_FK_FIELDS,
    CREDITS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
    STORY_ARC_NUMBERS_FIELD_NAME,
    UNIVERSES_FIELD_NAME,
)
from codex.models import (
    Credit,
    StoryArc,
    StoryArcNumber,
    Universe,
)
from codex.models.base import BaseModel
from codex.models.named import (
    CreditPerson,
    CreditRole,
    Identifier,
    IdentifierType,
)

FIELD_NAME_TO_MD_KEY_MAP = MappingProxyType(
    {
        STORY_ARC_NUMBERS_FIELD_NAME: ARCS_KEY,
    }
)
DICT_MODEL_AGG_MAP: MappingProxyType[str, dict[str, DeferredAttribute]] = (  # pyright: ignore[reportAssignmentType]
    MappingProxyType(
        {
            CREDITS_FIELD_NAME: {ROLES_KEY: CreditRole.name},
            IDENTIFIERS_FIELD_NAME: {NSS_KEY: Identifier.nss, URL_KEY: Identifier.url},
            STORY_ARC_NUMBERS_FIELD_NAME: {NUMBER_KEY: StoryArcNumber.number},
            UNIVERSES_FIELD_NAME: {
                DESIGNATION_KEY: Universe.designation,
            },
        }
    )
)
DICT_MODEL_SUB_MODEL: MappingProxyType[type[BaseModel], type[BaseModel]] = (
    MappingProxyType(
        {
            Credit: CreditPerson,
            Identifier: IdentifierType,
            StoryArcNumber: StoryArc,
        }
    )
)
DICT_MODEL_SUB_SUB_KEY = MappingProxyType(
    {
        ROLES_KEY: CreditRole,
    }
)
COMIC_FK_FIELD_NAMES: MappingProxyType[str, Field] = MappingProxyType(
    {
        **{
            field.name: field.related_model._meta.get_field("name")
            for field in COMIC_FK_FIELDS
            if field.related_model and field.name not in PROTAGONIST_FIELD_MODEL_MAP
        },
        PROTAGONIST_KEY: PROTAGONIST_FIELD_MODEL_MAP["main_character"]._meta.get_field(
            "name"
        ),
    }
)
