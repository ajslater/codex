"""
Shared queryset shape for ``GroupSerializer`` consumers.

The metadata view emits ``*_list`` fields populated by
``codex.serializers.browser.metadata.GroupSerializer``, which expects
each row to expose ``ids``, ``name`` (and ``number_to`` for Volume).
Two call sites populate these lists — parent groups in
``MetadataQueryIntersectionsView._query_groups`` and the current group
in ``MetadataCopyIntersectionsView._highlight_current_group`` — so the
projection lives here to keep them from drifting.
"""

from types import MappingProxyType

from django.db.models import QuerySet

from codex.models import BrowserGroupModel
from codex.models.functions import JsonGroupArray
from codex.models.groups import Volume

# Model class names whose ``*_list`` attribute name on the metadata
# response object doesn't match ``__name__.lower() + "_list"``.
# ``StoryArc.__name__.lower() == "storyarc"`` but the serializer reads
# ``story_arc_list``; without this map the populated attribute would
# silently fall on the floor.
_GROUP_LIST_FIELD_OVERRIDES = MappingProxyType({"StoryArc": "story_arc_list"})


def group_list_field_name(model: type[BrowserGroupModel]) -> str:
    """Return the metadata-obj attribute the serializer reads for ``model``."""
    name = model.__name__
    return _GROUP_LIST_FIELD_OVERRIDES.get(name, name.lower() + "_list")


def annotate_group_list(qs: QuerySet) -> QuerySet:
    """Project a pre-filtered BrowserGroupModel qs into ``GroupSerializer`` shape."""
    only = ["name", "number_to"] if qs.model is Volume else ["name"]
    return (
        qs.only(*only)
        .distinct()
        .group_by(*only)  # pyright: ignore[reportAttributeAccessIssue]
        .annotate(ids=JsonGroupArray("id", distinct=True, order_by="id"))
        .values("ids", *only)
    )
