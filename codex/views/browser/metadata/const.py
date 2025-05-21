"""Metadata view consts."""

from types import MappingProxyType

from codex.models import Comic
from codex.models.groups import Imprint, Publisher, Series, Volume
from codex.models.named import Credit, Identifier, StoryArcNumber, Universe

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
_CREDIT_RELATIONS = ("role", "person")
GROUP_MODELS = MappingProxyType(
    {
        "i": (Publisher,),
        "s": (Publisher, Imprint),
        "v": (Publisher, Imprint, Series),
        "c": (Publisher, Imprint, Series, Volume),
        "f": (Publisher, Imprint, Series, Volume),
        "a": (Publisher, Imprint, Series, Volume),
    }
)
M2M_QUERY_OPTIMIZERS = MappingProxyType(
    {
        Credit: {
            "prefetch": _CREDIT_RELATIONS,
            "only": _CREDIT_RELATIONS,
        },
        StoryArcNumber: {"select": ("story_arc",), "only": ("story_arc", "number")},
        Identifier: {
            "select": ("identifier_type",),
            "only": ("identifier_type", "nss", "url"),
        },
        Universe: {"only": ("name", "designation")},
    }
)
COMIC_MAIN_FIELD_NAME_BACK_REL_MAP = MappingProxyType(
    {
        "main_character": "main_character_in_comics",
        "main_team": "main_team_in_comics",
    }
)
