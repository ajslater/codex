"""Metadata view consts."""

from types import MappingProxyType

from codex.models import BrowserGroupModel, Comic
from codex.models.age_rating import AgeRating
from codex.models.groups import Folder, Imprint, Publisher, Series, Volume
from codex.models.identifier import Identifier
from codex.models.named import (
    Character,
    Credit,
    SeriesGroup,
    StoryArcNumber,
    Team,
    Universe,
)

############
# Annotate #
############
COMIC_VALUE_FIELDS_CONFLICTING = frozenset(
    {
        "created_at",
        "name",
        "path",
        "updated_at",
    }
)
COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
PATH_GROUPS = frozenset({"c", "f"})
ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS = frozenset({"path"})
_DISABLED_VALUE_FIELD_NAMES = frozenset(
    {"id", "pk", "sort_name", "stat"} | COMIC_VALUE_FIELDS_CONFLICTING
)
COMIC_VALUE_FIELD_NAMES = frozenset(
    # contains path
    field.name
    for field in Comic._meta.get_fields()
    if not field.is_relation and field.name not in _DISABLED_VALUE_FIELD_NAMES
)
COMIC_RELATED_VALUE_FIELDS = frozenset({"series__volume_count", "volume__issue_count"})
SUM_FIELDS = frozenset({"page_count", "size"})

#########
# Query #
#########
_CREDIT_ONLY = ("role", "person")
_CREDIT_PREFETCH = (*_CREDIT_ONLY, "role__identifier", "person__identifier")
GROUP_MODELS: MappingProxyType[str, tuple[type[BrowserGroupModel], ...]] = (
    MappingProxyType(
        {
            "i": (Publisher,),
            "s": (Publisher, Imprint),
            "v": (Publisher, Imprint, Series),
            "c": (Publisher, Imprint, Series, Volume),
            "f": (Publisher, Imprint, Series, Volume),
            "a": (Publisher, Imprint, Series, Volume),
        }
    )
)
M2M_QUERY_OPTIMIZERS = MappingProxyType(
    {
        Credit: {
            "prefetch": _CREDIT_PREFETCH,
            "select": (),
            "only": _CREDIT_ONLY,
        },
        StoryArcNumber: {
            "prefetch": ("story_arc", "story_arc__identifier"),
            "select": (),
            "only": ("story_arc", "number"),
        },
        Identifier: {
            "select": ("source",),
            "only": ("source", "key", "url"),
        },
        Universe: {"only": ("name", "designation", "identifier")},
        SeriesGroup: {
            "select": (),
            "only": ("name",),
        },
        Folder: {
            "select": (),
            "only": ("path",),
        },
    }
)
COMIC_MAIN_FIELD_NAME_BACK_REL_MAP = MappingProxyType(
    {
        "main_character": "main_character_in_comics",
        "main_team": "main_team_in_comics",
    }
)
# Per-FK-model select_related + only() hints so .first() hydrates the
# nested FKs the metadata serializers read (e.g. AgeRating.metron,
# Character.identifier.url). Without these the serializer fires an
# extra query per nested access; 3 FK models have such nestings today.
_IDENTIFIED_ONLY = ("name", "identifier__url")
_IDENTIFIED_OPT = MappingProxyType(
    {"select": ("identifier",), "only": _IDENTIFIED_ONLY}
)
FK_QUERY_OPTIMIZERS = MappingProxyType(
    {
        AgeRating: {
            "select": ("metron",),
            "only": ("name", "metron__name", "metron__index"),
        },
        Character: _IDENTIFIED_OPT,
        Team: _IDENTIFIED_OPT,
    }
)
