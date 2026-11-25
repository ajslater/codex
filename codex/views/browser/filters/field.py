"""Comic field filters."""

from collections.abc import Collection
from types import MappingProxyType

from django.db.models.query_utils import Q

from codex.models import Comic
from codex.views.browser.const import BROWSER_FILTER_KEYS, MATCH_ALL_KEY
from codex.views.browser.filters.collection import CollectionFilterView
from codex.views.browser.filters.reading_lists import (
    READING_LIST_KIND_FILTER,
    READING_LISTS_FILTER,
    held_lists_filter,
    list_kind_filter,
    reading_lists_filter,
)
from codex.views.settings import CREDIT_PERSON_UI_FIELD, IDENTIFIER_TYPE_UI_FIELD

_FILTER_REL_MAP = MappingProxyType(
    {
        CREDIT_PERSON_UI_FIELD: "credits__person",
        IDENTIFIER_TYPE_UI_FIELD: "identifiers__source",
        # Both age-rating filters route through the ``Comic.age_rating`` FK.
        # The tagged filter uses :class:`AgeRating` PKs (matching the tagged
        # name); the metron filter uses :class:`AgeRatingMetron` PKs reached
        # via the ``age_rating__metron`` chain.
        "age_rating_tagged": "age_rating",
        "age_rating_metron": "age_rating__metron",
        # Series attributes filter every comic of the series.
        "series_end_year": "series__end_year",
        "series_start_year": "series__start_year",
        "series_status": "series__status",
    }
)
_FILTER_ATTRIBUTES: frozenset[str] = frozenset(BROWSER_FILTER_KEYS)
_KIND_SKIPPED = frozenset({READING_LIST_KIND_FILTER})
_GRID_SKIPPED_FILTERS = frozenset({READING_LIST_KIND_FILTER, READING_LISTS_FILTER})
# Filters whose "None" choice is a blank string column, never NULL.
_FILTER_BLANK_NULL_FIELDS: frozenset[str] = frozenset({"series_status"})
_NOTHING = Q(pk__in=())


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

    @staticmethod
    def _null_q(field: str, rel: str) -> Q:
        """Match the "None" choice for a filter field."""
        query = Q(**{f"{rel}__isnull": True})
        if field in _FILTER_BLANK_NULL_FIELDS:
            query |= Q(**{rel: ""})
        return query

    @classmethod
    def _match_every_value(
        cls, field: str, rel_prefix: str, comic_rel: str, values, *, match_null: bool
    ) -> Q:
        """
        Under All: the comics holding every ticked value.

        One ``IN`` subquery per value, ANDed: a join would repeat the comic
        row per matching value and multiply the sums. No comic has no value
        and a value, so None with another value matches nothing; None alone
        is the comics with no value, as under Any.
        """
        if match_null:
            if values:
                return _NOTHING
            matches = (Comic.objects.filter(cls._null_q(field, comic_rel)),)
        else:
            matches = (Comic.objects.filter(**{comic_rel: value}) for value in values)
        query = Q()
        for comics in matches:
            query &= Q(**{f"{rel_prefix}pk__in": comics.values("pk")})
        return query

    @classmethod
    def _filter_by_comic_field(
        cls, field, rel_prefix, filter_list, *, match_all: bool = False
    ) -> Q:
        """Filter by a comic any2many attribute; under All, by every value."""
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
            if match_all:
                return cls._match_every_value(
                    field,
                    rel_prefix,
                    comic_rel,
                    non_null_filter_list,
                    match_null=match_null,
                )
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
                inner |= cls._null_q(field, comic_rel)
            if non_null_filter_list:
                inner |= Q(**{f"{comic_rel}__in": non_null_filter_list})
            comic_pks = Comic.objects.filter(inner).values("pk")
            return Q(**{f"{rel_prefix}pk__in": comic_pks})

        if match_null:
            filter_query |= cls._null_q(field, rel)
        if non_null_filter_list:
            filter_query |= Q(**{f"{rel}__in": non_null_filter_list})
        return filter_query

    @classmethod
    def get_all_comic_field_filters(cls, rel_prefix, filters, user) -> Q:
        """
        Get all comic field filters for rel_prefix.

        ``user`` scopes the reading lists filter to the lists they may see.
        A filter named in ``match_all`` matches every ticked value, not any.
        """
        match_all = frozenset(filters.get(MATCH_ALL_KEY) or ())
        comic_field_filter = Q()
        # Only walk keys that are both valid AND set in this request's
        # filters - saves ~20 no-op `_filter_by_comic_field` calls per
        # request on typical browsers that set 0-2 field filters.
        for field in _FILTER_ATTRIBUTES & filters.keys():
            filter_list = filters.get(field)
            if not filter_list:
                continue
            every = field in match_all
            if field == READING_LISTS_FILTER:
                comic_field_filter &= reading_lists_filter(
                    rel_prefix, filter_list, user, match_all=every
                )
            elif field == READING_LIST_KIND_FILTER:
                comic_field_filter &= list_kind_filter(rel_prefix, filter_list, user)
            else:
                comic_field_filter &= cls._filter_by_comic_field(
                    field, rel_prefix, filter_list, match_all=every
                )
        return comic_field_filter

    def _skipped_filters(self, model, collection, pks) -> frozenset[str]:
        """
        Return the filters that do not narrow by the lists' comics here.

        On the grid of lists the kind and the Reading Lists filter pick the
        lists themselves. Inside one list the kind does nothing.
        """
        if self.is_lists_grid(model, collection, pks):
            return _GRID_SKIPPED_FILTERS
        if self.is_in_lists(collection, pks):
            return _KIND_SKIPPED
        return frozenset()

    def get_comic_field_filter(
        self, model, collection=None, pks=None, *, omit: Collection[str] = ()
    ) -> Q:
        """
        Filter the comics based on the form filters.

        On the grid of lists the Reading Lists filter shows the lists the
        chosen lists hold; every other filter still narrows by the lists'
        comics. Inside one list it narrows the comics like any filter, and
        the kind does nothing. Elsewhere the kind narrows to comics on a
        list of that kind. ``omit`` names filters to leave out entirely:
        apart from the skipped ones, so leaving the Reading Lists filter
        out of a comic query never puts the held lists' pks on it.
        """
        rel_prefix = self.get_rel_prefix(model)
        filters = {k: v for k, v in self.params["filters"].items() if k not in omit}
        user = self.request.user
        skipped = self._skipped_filters(model, collection, pks)
        others = {k: v for k, v in filters.items() if k not in skipped}
        query = self.get_all_comic_field_filters(rel_prefix, others, user)
        if READING_LISTS_FILTER in skipped and (
            held := filters.get(READING_LISTS_FILTER)
        ):
            every = READING_LISTS_FILTER in (filters.get(MATCH_ALL_KEY) or ())
            query &= held_lists_filter(held, user, match_all=every)
        return query
