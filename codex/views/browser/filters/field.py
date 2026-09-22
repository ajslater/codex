"""Comic field filters."""

from types import MappingProxyType

from django.db.models.query_utils import Q

from codex.models import Comic
from codex.views.browser.const import BROWSER_FILTER_KEYS
from codex.views.browser.filters.collection import CollectionFilterView
from codex.views.settings import (
    CREDIT_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
    STORY_ARC_UI_FIELD,
)

_FILTER_REL_MAP = MappingProxyType(
    {
        CREDIT_PERSON_UI_FIELD: "credits__person",
        STORY_ARC_UI_FIELD: "story_arc_numbers__story_arc",
        IDENTIFIER_TYPE_UI_FIELD: "identifiers__source",
        # Both age-rating filters route through the ``Comic.age_rating`` FK.
        # The tagged filter uses :class:`AgeRating` PKs (matching the tagged
        # name); the metron filter uses :class:`AgeRatingMetron` PKs reached
        # via the ``age_rating__metron`` chain.
        "age_rating_tagged": "age_rating",
        "age_rating_metron": "age_rating__metron",
    }
)
_FILTER_ATTRIBUTES: frozenset[str] = frozenset(BROWSER_FILTER_KEYS)


class ComicFieldFilterView(CollectionFilterView):
    """Comic field filters."""

    @staticmethod
    def _is_multivalued(comic_rel: str) -> bool:
        """Whether a Comic-relative relation path can fan a comic row out."""
        model = Comic
        for part in comic_rel.split("__"):
            field = model._meta.get_field(part)
            if field.many_to_many or field.one_to_many:
                return True
            model = field.related_model
            if model is None:
                break
        return False

    @classmethod
    def _filter_by_comic_field(cls, field, rel_prefix, filter_list) -> Q:
        """Filter by a comic any2many attribute."""
        filter_query = Q()
        if not filter_list:
            return filter_query

        comic_rel = _FILTER_REL_MAP.get(field, field)
        rel = rel_prefix + comic_rel

        # ``None`` is a sentinel meaning "match the null relation"; the
        # ORM ``__in`` lookup can't express it, so partition first and
        # combine. The previous shape mutated ``filter_list`` mid-loop
        # via ``del filter_list[index]`` which only worked because at
        # most one ``None`` was ever present in practice.
        non_null_filter_list = [val for val in filter_list if val is not None]
        match_null = len(non_null_filter_list) != len(filter_list)

        if cls._is_multivalued(comic_rel):
            # A multi-valued relation JOINed inline repeats the comic row
            # once per matching tag, which silently multiplies every
            # collection-row ``Sum`` downstream (a comic matching 2 of the
            # filtered characters doubled its page_count). Testing set
            # membership instead keeps the predicate per *comic*: same
            # rows, one uncorrelated sub-SELECT that SQLite materializes
            # once, and measurably faster than the join (a filtered
            # publishers browse over 18k comics: 52ms -> 32ms).
            inner = Q()
            if match_null:
                inner |= Q(**{f"{comic_rel}__isnull": True})
            if non_null_filter_list:
                inner |= Q(**{f"{comic_rel}__in": non_null_filter_list})
            comic_pks = Comic.objects.filter(inner).values("pk")
            return Q(**{f"{rel_prefix}pk__in": comic_pks})

        if match_null:
            filter_query |= Q(**{f"{rel}__isnull": True})
        if non_null_filter_list:
            filter_query |= Q(**{f"{rel}__in": non_null_filter_list})
        return filter_query

    @classmethod
    def get_all_comic_field_filters(cls, rel_prefix, filters) -> Q:
        """Get all comicfiled filters for rel_prefix."""
        comic_field_filter = Q()
        # Only walk keys that are both valid AND set in this request's
        # filters - saves ~20 no-op `_filter_by_comic_field` calls per
        # request on typical browsers that set 0-2 field filters.
        for field in _FILTER_ATTRIBUTES & filters.keys():
            filter_list = filters.get(field)
            if not filter_list:
                continue
            comic_field_filter &= cls._filter_by_comic_field(
                field, rel_prefix, filter_list
            )
        return comic_field_filter

    def get_comic_field_filter(self, model) -> Q:
        """Filter the comics based on the form filters."""
        rel_prefix = self.get_rel_prefix(model)
        filters = self.params["filters"]
        return self.get_all_comic_field_filters(rel_prefix, filters)
