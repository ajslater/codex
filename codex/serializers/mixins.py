"""Serializer mixins."""
from django.db.models import F, Q
from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.db_functions import GroupConcat


UNIONFIX_PREFIX = "unionfix_"
COMIC_M2M_NAME_FIELDS = frozenset(
    (
        "characters",
        "genres",
        "locations",
        "series_groups",
        "story_arcs",
        "tags",
        "teams",
    )
)
AUTHOR_ROLES = set(("Writer", "Author", "Plotter", "Scripter", "Creator"))
AUTHOR_ROLES_QUERY = {"credits__role__name__in": AUTHOR_ROLES}


class BrowserAggregateBaseSerializerMixin(Serializer):
    """Mixin for browser, opds & metadata serializers."""

    group = CharField(read_only=True, max_length=1, source=UNIONFIX_PREFIX + "group")

    # Aggregate Annotations
    child_count = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "child_count")
    cover_pk = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "cover_pk")

    # Bookmark annotations
    page = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "page")


class BrowserAggregateSerializerMixin(BrowserAggregateBaseSerializerMixin):
    """Mixin for browser & metadata serializers."""

    finished = BooleanField(read_only=True, source=UNIONFIX_PREFIX + "finished")
    progress = DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
        coerce_to_string=False,
        source=UNIONFIX_PREFIX + "progress",
    )


class BrowserCardOPDSBaseSerializer(BrowserAggregateSerializerMixin):
    """Common base for Browser Card and OPDS serializer."""

    pk = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "pk")
    publisher_name = CharField(
        read_only=True, source=UNIONFIX_PREFIX + "publisher_name"
    )
    series_name = CharField(read_only=True, source=UNIONFIX_PREFIX + "series_name")
    volume_name = CharField(read_only=True, source=UNIONFIX_PREFIX + "volume_name")
    name = CharField(read_only=True, source=UNIONFIX_PREFIX + "name")
    issue = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
        source=UNIONFIX_PREFIX + "issue",
    )
    issue_suffix = CharField(read_only=True, source=UNIONFIX_PREFIX + "issue_suffix")
    order_value = CharField(read_only=True, source=UNIONFIX_PREFIX + "order_value")
    page_count = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "page_count")


def _get_credit_persons(authors=False):
    """Get credit persons as a csv."""
    if authors:
        filter = Q(**AUTHOR_ROLES_QUERY)
    else:
        filter = ~Q(**AUTHOR_ROLES_QUERY)

    return GroupConcat("credits__person__name", distinct=True, filter=filter)


def get_serializer_values_map(serializers, copy_only=False, folders=False):
    """Create map for ordering values() properly with the UNIONFIX_PREFIX."""
    # Fixes Django's requirement that unions have the same field order, but Django
    # provides no mechanism to actually order fields.
    # copy_only is for metadata view.
    # folders is for OPDS folders view.
    fields = {}
    for serializer in serializers:
        fields.update(serializer().get_fields())
    fields = sorted(fields)
    result = {}
    for field in fields:
        if copy_only:
            val = field
        else:
            if field in COMIC_M2M_NAME_FIELDS and not folders:
                val = GroupConcat(f"{field}__name", distinct=True)
            elif field in ("contributors", "authors"):
                if folders:
                    val = F("credits")
                else:
                    val = _get_credit_persons(field == "authors")
            else:
                val = F(field)
        result[UNIONFIX_PREFIX + field] = val
    return result


class OKSerializer(Serializer):
    """Default serializer for views without much response."""

    ok = BooleanField(default=True)
