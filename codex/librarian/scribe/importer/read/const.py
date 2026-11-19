"""Aggregate Consts."""

from types import MappingProxyType

from comicbox.formats.comicbox.schema import (
    ARCS_KEY,
    CHARACTERS_KEY,
    DESIGNATION_KEY,
    GENRES_KEY,
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
from comicbox.identifiers import ID_KEY_KEY
from django.db.models.fields import Field

from codex.librarian.scribe.importer.const import (
    ALL_COMIC_FK_FIELDS,
    ALWAYS_UPDATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS_SET,
    COLLECTION_FIELD_NAMES,
    COLLECTION_FIELD_NAMES_SET,
    COMIC_M2M_FIELD_NAMES,
    CREDITS_FIELD_NAME,
    FOLDERS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    NAME_FIELD_NAME,
    PATH_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
    STORY_ARC_NUMBERS_FIELD_NAME,
    UNIVERSES_FIELD_NAME,
)
from codex.models import (
    Comic,
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
# Every lookup a comic's tags set, collections first, in the order each
# names its parent. A tag read sets them all: a collection the tags don't
# name is the default one, any other lookup they don't set is unset.
TAG_FK_FIELD_NAMES: tuple[str, ...] = (
    *COLLECTION_FIELD_NAMES,
    *sorted(COMIC_FK_FIELD_NAMES - COLLECTION_FIELD_NAMES_SET),
)

##########
# Scalar #
##########
# What codex reads off the archive or its path rather than its tags.
_ENVELOPE_COMIC_FIELD_NAMES = frozenset(
    {"file_type", "metadata_mtime", "page_count", PATH_FIELD_NAME}
)
# The Comic columns a comic's tags set: not what presave derives, nor the
# envelope. A tag read gives a file's comic the default of each it lacks,
# as a fresh import of the file would.
TAG_COMIC_FIELDS: tuple[Field, ...] = tuple(
    field
    for field in Comic._meta.concrete_fields
    if not field.is_relation
    and field.name in BULK_UPDATE_COMIC_FIELDS_SET
    and field.name not in ALWAYS_UPDATE_COMIC_FIELDS
    and field.name not in _ENVELOPE_COMIC_FIELD_NAMES
)

#######
# M2M #
#######
# Every m2m a comic's tags set: all but its folders, which its path sets.
# A tag read sets them all, so a field the tags hold nothing for links
# nothing.
TAG_M2M_FIELD_NAMES: tuple[str, ...] = tuple(
    field_name
    for field_name in COMIC_M2M_FIELD_NAMES
    if field_name != FOLDERS_FIELD_NAME
)
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
# Marks a reprint that came from the series' other names rather than
# from a list of reprints. Codex stores both in one table, so the two
# lists are merged before aggregation and this rides along to say which
# list a row came from. Underscored so it cannot collide with a comicbox
# key.
ALTERNATIVE_NAME_MARKER = "_alternative_name"
# This map tells aggregator how to parse metadata into tuples for query & create.
COMPLEX_FIELD_AGG_MAP: MappingProxyType[str, tuple] = MappingProxyType(
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
                ID_KEY_KEY: Identifier.key,
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
