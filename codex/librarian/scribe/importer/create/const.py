"""Create fks consts."""

from collections.abc import Mapping
from types import MappingProxyType

from codex.librarian.scribe.importer.const import (
    CREDIT_PERSON_FIELD_NAME,
    CREDIT_ROLE_FIELD_NAME,
    DESIGNATION_FIELD_NAME,
    IDENTIFIED_MODELS,
    IDENTIFIER_FIELD_NAME,
    IDENTIFIER_ID_KEY_FIELD_NAME,
    IDENTIFIER_SOURCE_FIELD_NAME,
    IDENTIFIER_TYPE_FIELD_NAME,
    IDENTIFIER_URL_FIELD_NAME,
    IMPRINT_FIELD_NAME,
    ISSUE_COUNT_FIELD_NAME,
    NAME_FIELD_NAME,
    NAMED_MODELS,
    NUMBER_FIELD_NAME,
    NUMBER_TO_FIELD_NAME,
    PUBLISHER_FIELD_NAME,
    SERIES_FIELD_NAME,
    STORY_ARC_FIELD_NAME,
    VOLUME_COUNT_FIELD_NAME,
)
from codex.models import (
    Credit,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.base import BaseModel
from codex.models.comic import Comic
from codex.models.groups import Folder, Imprint, Publisher, Series
from codex.models.identifier import (
    Identifier,
    IdentifierSource,
)
from codex.models.named import (
    CreditPerson,
    CreditRole,
    Universe,
)

ORDERED_CREATE_MODELS = (
    IdentifierSource,
    Identifier,
    Publisher,
    Imprint,
    Series,
    Volume,
)

CUSTOM_COVER_MODELS = frozenset({Publisher, Imprint, Series, Volume, Folder, StoryArc})
GROUP_BASE_MODELS = frozenset({Publisher, Imprint, Series, StoryArc})
GROUP_BASE_FIELDS = ("name", "sort_name")
DEFAULT_NON_NULL_CHARFIELD_NAMES = frozenset({"name"})
NON_NULL_CHARFIELD_NAMES: MappingProxyType[type[BaseModel], frozenset[str]] = (
    MappingProxyType(
        {
            Universe: frozenset({"designation"}),
            Identifier: frozenset({"id_type", "key", "url"}),
            Comic: frozenset({"path"}),
            Volume: frozenset({}),
        }
    )
)
_NAMED_CREATE_ARGS = ({NAME_FIELD_NAME: None}, {})
_IDENTIFIED_CREATE_ARGS = ({NAME_FIELD_NAME: None}, {IDENTIFIER_FIELD_NAME: Identifier})
MODEL_CREATE_ARGS_MAP: MappingProxyType[
    type[BaseModel], tuple[Mapping[str, type[BaseModel] | None], ...]
] = MappingProxyType(
    {
        **dict.fromkeys(NAMED_MODELS, _NAMED_CREATE_ARGS),
        Identifier: (
            {
                IDENTIFIER_SOURCE_FIELD_NAME: IdentifierSource,
                IDENTIFIER_TYPE_FIELD_NAME: None,
                IDENTIFIER_ID_KEY_FIELD_NAME: None,
            },
            {
                IDENTIFIER_URL_FIELD_NAME: None,
            },
        ),
        Publisher: _IDENTIFIED_CREATE_ARGS,
        Imprint: (
            {
                PUBLISHER_FIELD_NAME: Publisher,
                NAME_FIELD_NAME: None,
            },
            {IDENTIFIER_FIELD_NAME: Identifier},
        ),
        Series: (
            {
                PUBLISHER_FIELD_NAME: Publisher,
                IMPRINT_FIELD_NAME: Imprint,
                NAME_FIELD_NAME: None,
            },
            {IDENTIFIER_FIELD_NAME: Identifier, VOLUME_COUNT_FIELD_NAME: None},
        ),
        Volume: (
            {
                PUBLISHER_FIELD_NAME: Publisher,
                IMPRINT_FIELD_NAME: Imprint,
                SERIES_FIELD_NAME: Series,
                NAME_FIELD_NAME: None,
                NUMBER_TO_FIELD_NAME: None,
            },
            {ISSUE_COUNT_FIELD_NAME: None},
        ),
        **dict.fromkeys(IDENTIFIED_MODELS, _IDENTIFIED_CREATE_ARGS),
        Credit: (
            {
                CREDIT_PERSON_FIELD_NAME: CreditPerson,
                CREDIT_ROLE_FIELD_NAME: CreditRole,
            },
            {},
        ),
        StoryArcNumber: ({STORY_ARC_FIELD_NAME: StoryArc, NUMBER_FIELD_NAME: None}, {}),
        Universe: (
            {
                NAME_FIELD_NAME: None,
            },
            {
                IDENTIFIER_FIELD_NAME: Identifier,
                DESIGNATION_FIELD_NAME: None,
            },
        ),
    }
)
