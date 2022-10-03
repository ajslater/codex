"""Base view for metadata annotations."""
from os import sep

from django.db.models import (
    Avg,
    BooleanField,
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.fields import PositiveSmallIntegerField
from django.db.models.functions import Least, Lower, Reverse, Right, StrIndex, Substr

from codex.models import Comic, Folder, Imprint, Publisher, Series, Volume
from codex.serializers.mixins import UNIONFIX_PREFIX
from codex.views.browser.base import BrowserBaseView


class BrowserMetadataBaseView(BrowserBaseView):
    """Base class for views that need special metadata annotations."""

    _ORDER_BY_FIELD_ALIASES = {"search_score": "searchresult__score"}
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
        "searchresult__score": Min,
    }
    _NO_SEARCH_SCORE = Value(None, IntegerField())
    _UNIONFIX_DEFAULT_ORDERING = tuple(
        UNIONFIX_PREFIX + field.replace("__", "_") for field in Comic.ORDERING
    )
    _ORDER_VALUE_ORDERING = (UNIONFIX_PREFIX + "order_value", UNIONFIX_PREFIX + "pk")
    _HALF_VALUE = Value(0.5)
    _SEP_VALUE = Value(sep)
    _ONE_INTEGERFIELD = Value(1, IntegerField())
    NONE_CHARFIELD = Value(None, CharField())
    GROUP_MODEL_MAP = {
        BrowserBaseView.ROOT_GROUP: None,
        "p": Publisher,
        "i": Imprint,
        "s": Series,
        "v": Volume,
        BrowserBaseView.COMIC_GROUP: Comic,
        BrowserBaseView.FOLDER_GROUP: Folder,
    }
    ARTICLES = frozenset(
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

    @staticmethod
    def _cover_subquery(cover_comics, field):
        """Create cover subquery for each field."""
        return Subquery(cover_comics.values(f"comic__{field}")[:1])

    def get_order_key(self):
        """Get the default order key for the view."""
        order_key = self.params.get("order_by")
        if not order_key:
            group = self.kwargs.get("group")
            if group == self.FOLDER_GROUP:
                order_key = "path"
            else:
                order_key = "sort_name"
        return order_key

    def _annotate_cover_pk(self, queryset, model):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the descendant comics by the sort argumentst
        if model == Comic:
            cover_pk = F("pk")
        else:
            # This creates two subqueries. It would be better condensed into one.
            # but there's no way to annotate an object or multiple values.
            qs = queryset.filter(pk=OuterRef("pk"))
            cover_comics = self.get_order_by(Comic, qs, for_cover_pk=True)
            cover_pk = self._cover_subquery(cover_comics, "pk")
        queryset = queryset.annotate(cover_pk=cover_pk)
        return queryset

    def _annotate_page_count(self, obj_list):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        page_count_sum = Sum("comic__page_count")
        obj_list = obj_list.annotate(page_count=page_count_sum)
        return obj_list

    def _annotate_bookmarks(self, obj_list, is_model_comic):
        """Hoist up bookmark annoations."""
        bm_rel = self.get_bm_rel(is_model_comic)
        bm_filter = self._get_my_bookmark_filter(bm_rel)

        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if is_model_comic:
            # Hoist up the bookmark and finished states
            bookmark_page = Sum(
                page_rel,
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            finished_aggregate = Sum(
                finished_rel,
                default=False,
                filter=bm_filter,
                output_field=BooleanField(),
            )
        else:
            # Aggregate bookmark and finished states
            bookmark_page = Sum(
                Case(
                    When(**{bm_rel: None}, then=0),
                    When(**{finished_rel: True}, then="comic__page_count"),
                    default=page_rel,
                    output_field=PositiveSmallIntegerField(),
                ),
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            finished_count = Sum(
                finished_rel,
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
            )
            obj_list = obj_list.annotate(finished_count=finished_count)
            finished_aggregate = Case(
                When(
                    Q(finished_count=F("child_count")) | Q(page=F("page_count")),
                    then=True,
                ),
                When(page=0, then=False),
                default=None,
                output_field=BooleanField(),
            )

        obj_list = obj_list.annotate(
            page=bookmark_page,
            finished=finished_aggregate,
        )

        return obj_list

    @staticmethod
    def _annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        then = Least(F("page") * 100.0 / F("page_count"), Value(100.0))
        progress = Case(When(page_count__gt=0, then=then), default=0.0)
        queryset = queryset.annotate(progress=progress)
        return queryset

    @classmethod
    def _get_path_query_func(cls, field):
        """Use the db to get only the filename."""
        return Right(
            field, StrIndex(Reverse(field), cls._SEP_VALUE) - 1  # type: ignore
        )

    def get_aggregate_func(self, order_key, model, autoquery_pk=None):
        """Get a complete function for aggregating an attribute."""
        # Get field from order_key
        if order_key == "search_score":
            if not autoquery_pk:
                return self._NO_SEARCH_SCORE
            field = "searchresult__score"
        elif order_key == "sort_name" or not order_key:
            field = None
        else:
            field = order_key

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

            filters = Q(comic__searchresult__query=autoquery_pk)
            func = agg_func(full_field, filters=filters)
        return func

    def annotate_common_aggregates(self, qs, model):
        """Annotate common aggregates between browser and metadata."""
        is_model_comic = model == Comic
        qs = self._annotate_cover_pk(qs, model)
        if is_model_comic:
            child_count_sum = self._ONE_INTEGERFIELD
        else:
            qs = self._annotate_page_count(qs)
            child_count_sum = Count("comic__pk", distinct=True)
        qs = qs.annotate(child_count=child_count_sum)
        qs = self._annotate_bookmarks(qs, is_model_comic)
        qs = self._annotate_progress(qs)
        return qs

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
                    lowercase_first_word__in=cls.ARTICLES,
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
        """
        Create the order_by list.

        Order on pk to give duplicates a consistent position.
        """
        # order_prefix
        prefix = "-" if self.params.get("order_reverse") else ""

        # order_fields
        order_key = self.get_order_key()
        if for_cover_pk:
            prefix += "comic__"
            field = self._ORDER_BY_FIELD_ALIASES.get(order_key, order_key)
            if field == "sort_name" or not field:
                ordering = Comic.ORDERING
            else:
                ordering = (field, "pk")
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
