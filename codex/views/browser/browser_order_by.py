"""Base view for ordering the query."""
from os import sep

from django.db.models import Avg, Case, CharField, F, Max, Min, Q, Sum, Value, When
from django.db.models.functions import Lower, Reverse, Right, StrIndex, Substr

from codex.models import Comic, Folder
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.views.browser.base import BrowserBaseView


class BrowserOrderByView(BrowserBaseView):
    """Base class for views that need ordering."""

    _ORDER_AGGREGATE_FUNCS = {
        "age_rating": Avg,
        "community_rating": Avg,
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "page_count": Sum,
        "path": Min,
        "size": Sum,
        "updated_at": Min,
        "search_score": Min,
    }
    _UNIONFIX_DEFAULT_ORDERING = tuple(
        UNIONFIX_PREFIX + field.replace("__", "_") for field in Comic.ORDERING
    )
    _ORDER_VALUE_ORDERING = (
        UNIONFIX_PREFIX + "order_value",
        *_UNIONFIX_DEFAULT_ORDERING,
    )
    _SEP_VALUE = Value(sep)
    _ARTICLES = frozenset(
        ("a", "an", "the")  # en
        + ("un", "unos", "unas", "el", "los", "la", "las")  # es
        + ("un", "une", "le", "les", "la", "les", "l'")  # fr
        + ("o", "a", "os")  # pt
        # pt "as" conflicts with English
        + ("der", "dem", "des", "das")  # de
        # de: "den & die conflict with English
        + ("il", "lo", "gli", "la", "le", "l'")  # it
        # it: "i" conflicts with English
        + ("de", "het", "een")  # nl
        + ("en", "ett")  # sw
        + ("en", "ei", "et")  # no
        + ("en", "et")  # da
        + ("el", "la", "els", "les", "un", "una", "uns", "unes", "na")  # ct
    )
    NONE_CHARFIELD = Value(None, CharField())

    def get_order_key(self):
        """Get the default order key for the view."""
        order_key = self.params.get("order_by")
        if not order_key:
            group = self.kwargs.get("group")
            order_key = "path" if group == self.FOLDER_GROUP else "sort_name"
        return order_key

    @classmethod
    def _get_path_query_func(cls, field):
        """Use the db to get only the filename."""
        return Right(
            field, StrIndex(Reverse(field), cls._SEP_VALUE) - 1  # type: ignore
        )

    def get_aggregate_func(self, order_key, model):
        """Get a complete function for aggregating an attribute."""
        field = None if order_key == "sort_name" or not order_key else order_key

        # Determine order func
        if not field:
            # use default sorting.
            func = self.NONE_CHARFIELD
        elif field == "path" and model in (Comic, Folder):
            # special path sorting.
            func = self._get_path_query_func(field)
        elif model == Comic:
            # agg_none uses group fields not comic fields.
            func = F(field)
        else:
            # order by aggregate.

            # get agg_func
            agg_func = self._ORDER_AGGREGATE_FUNCS[field]
            if agg_func == Min and self.params.get("order_reverse"):
                agg_func = Max

            # get full_field
            full_field = "comic__" + field
            if field == "path":
                full_field = self._get_path_query_func(full_field)

            func = agg_func(full_field)
        return func

    @classmethod
    def _order_without_articles(cls, queryset, ordering):
        """Sort by name ignoring articles."""
        first_field = ordering[0]
        queryset = queryset.annotate(
            first_space_index=StrIndex(first_field, Value(" "))
        )

        lowercase_first_word = Lower(
            Substr(first_field, 1, length=(F("first_space_index") - 1))  # type: ignore
        )
        queryset = queryset.annotate(
            lowercase_first_word=Case(
                When(Q(first_space_index__gt=0), then=lowercase_first_word)
            ),
            default=Value(""),
        )

        queryset = queryset.annotate(
            sort_name=Case(
                When(
                    lowercase_first_word__in=cls._ARTICLES,
                    then=Substr(
                        first_field, F("first_space_index") + 1  # type: ignore
                    ),
                ),
                default=first_field,
            )
        )
        ordering = ("sort_name", *ordering[1:])
        return queryset, ordering

    def get_order_by(self, model, queryset, for_cover_pk=False):
        """Create the order_by list.

        Order on pk to give duplicates a consistent position.
        """
        # order_prefix
        prefix = "-" if self.params.get("order_reverse") else ""

        # order_fields
        order_key = self.get_order_key()
        if for_cover_pk:
            prefix += "comic__"
            ordering = []
            if order_key and order_key != "sort_name":
                ordering += [order_key]
            ordering += [*Comic.ORDERING]
        elif order_key == "sort_name" or not order_key:
            # Use default sort
            if model in (Comic, Folder):
                ordering = self._UNIONFIX_DEFAULT_ORDERING
            else:
                ordering = model.ORDERING

            group = self.kwargs.get("group")
            if group != self.FOLDER_GROUP:
                # Can't annotate after union
                queryset, ordering = self._order_without_articles(queryset, ordering)
        else:
            # Use annotated order_value
            ordering = self._ORDER_VALUE_ORDERING

        # order_by
        # add prefixes to all order_by fields
        ordering = (prefix + field for field in ordering)
        return queryset.order_by(*ordering)
