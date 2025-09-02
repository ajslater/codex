"""Aggregate Consts."""

from types import MappingProxyType

from comicbox.schemas.comicbox import (
    ARCS_KEY,
    CHARACTERS_KEY,
    DESIGNATION_KEY,
    GENRES_KEY,
    ID_KEY_KEY,
    ID_URL_KEY,
    IDENTIFIERS_KEY,
    LOCATIONS_KEY,
    NUMBER_KEY,
    PROTAGONIST_KEY,
    ROLES_KEY,
    SERIES_GROUPS_KEY,
    STORIES_KEY,
    TAGS_KEY,
    TEAMS_KEY,
)
from django.db.models.fields import CharField, Field
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor
from django.db.models.query_utils import DeferredAttribute

from codex.librarian.scribe.importer.const import (
    ALL_COMIC_FK_FIELDS,
    CREDITS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    NAME_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
    STORY_ARC_NUMBERS_FIELD_NAME,
    UNIVERSES_FIELD_NAME,
)
from codex.models import (
    StoryArc,
    StoryArcNumber,
    Universe,
)
from codex.models.identifier import (
    Identifier,
    IdentifierSource,
)
from codex.models.named import (
    Character,
    CreditPerson,
    CreditRole,
    Genre,
    Location,
    SeriesGroup,
    Story,
    Tag,
    Team,
)

######
# FK #
######
_EXCLUDE_FIELD_NAMES = frozenset(PROTAGONIST_FIELD_MODEL_MAP.keys() | {"parent_folder"})
COMIC_FK_FIELD_NAMES_FIELD_MAP: MappingProxyType[str, Field] = MappingProxyType(
    {
        **{
            field.name: field.related_model._meta.get_field(NAME_FIELD_NAME)
            for field in ALL_COMIC_FK_FIELDS
            if field.related_model and field.name not in _EXCLUDE_FIELD_NAMES
        },
        PROTAGONIST_KEY: PROTAGONIST_FIELD_MODEL_MAP["main_character"]._meta.get_field(
            NAME_FIELD_NAME
        ),
    }
)
COMIC_FK_FIELD_NAMES: frozenset[str] = frozenset(COMIC_FK_FIELD_NAMES_FIELD_MAP.keys())

#######
# M2M #
#######
FIELD_NAME_TO_MD_KEY_MAP = MappingProxyType(
    {
        STORY_ARC_NUMBERS_FIELD_NAME: ARCS_KEY,
    }
)
SIMPLE_KEY_CLASS_MAP = MappingProxyType(
    {
        SERIES_GROUPS_KEY: SeriesGroup,
    }
)
IDENTIFIED_KEY_CLASS_MAP = MappingProxyType(
    {
        CHARACTERS_KEY: Character,
        GENRES_KEY: Genre,
        LOCATIONS_KEY: Location,
        STORIES_KEY: Story,
        TAGS_KEY: Tag,
        TEAMS_KEY: Team,
    }
)
ID_TYPE_KEY = "id_type"
# This map tells aggregator how to parse metadata into tuples for query & create.
COMPLEX_FIELD_AGG_MAP: MappingProxyType[
    str,
    tuple[
        DeferredAttribute | CharField,
        ForwardManyToOneDescriptor | None,
        dict[str, DeferredAttribute],
    ],
] = MappingProxyType(
    {
        **{key: (cls.name, None, {}) for key, cls in SIMPLE_KEY_CLASS_MAP.items()},
        **{
            key: (cls.name, cls.identifier, {})
            for key, cls in IDENTIFIED_KEY_CLASS_MAP.items()
        },
        CREDITS_FIELD_NAME: (
            CreditPerson.name,
            CreditPerson.identifier,
            {
                ROLES_KEY: CreditRole.name,
            },
        ),
        IDENTIFIERS_FIELD_NAME: (
            IdentifierSource.name,
            None,
            {
                ID_TYPE_KEY: "comic",
                ID_KEY_KEY: Identifier.key,
                ID_URL_KEY: Identifier.url,
            },
        ),
        STORY_ARC_NUMBERS_FIELD_NAME: (
            StoryArc.name,
            StoryArc.identifier,
            {
                NUMBER_KEY: StoryArcNumber.number,
            },
        ),
        UNIVERSES_FIELD_NAME: (
            Universe.name,
            None,
            {
                IDENTIFIERS_KEY: Universe.identifier,
                DESIGNATION_KEY: Universe.designation,
            },
        ),
    }
)
