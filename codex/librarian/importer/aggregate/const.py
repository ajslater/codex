"""Aggregate Consts."""

from types import MappingProxyType

from comicbox.identifiers.const import NSS_KEY, URL_KEY
from comicbox.schemas.comicbox import (
    ARCS_KEY,
    CREDITS_KEY,
    IDENTIFIERS_KEY,
    NUMBER_KEY,
    ROLES_KEY,
)
from django.db.models.fields import Field
from django.db.models.query_utils import DeferredAttribute

from codex.librarian.importer.const import (
    COMIC_FK_FIELDS,
    CONTRIBUTORS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
)
from codex.models import (
    Contributor,
    StoryArc,
    StoryArcNumber,
)
from codex.models.named import (
    ContributorPerson,
    ContributorRole,
    Identifier,
    IdentifierType,
)

FIELD_NAME_TO_MD_KEY_MAP = MappingProxyType(
    {STORY_ARC_NUMBERS_FIELD_NAME: ARCS_KEY, CONTRIBUTORS_FIELD_NAME: CREDITS_KEY}
)
DICT_MODEL_AGG_MAP: MappingProxyType[str, dict[str, DeferredAttribute]] = (  # pyright: ignore[reportAssignmentType]
    MappingProxyType(
        {
            CONTRIBUTORS_FIELD_NAME: {ROLES_KEY: ContributorRole.name},
            IDENTIFIERS_FIELD_NAME: {NSS_KEY: Identifier.nss, URL_KEY: Identifier.url},
            STORY_ARC_NUMBERS_FIELD_NAME: {NUMBER_KEY: StoryArcNumber.number},
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
COMIC_FK_FIELD_NAMES: MappingProxyType[str, Field] = MappingProxyType(
    {
        field.name: field.related_model._meta.get_field("name")
        for field in COMIC_FK_FIELDS
        if field.related_model
    }
)
