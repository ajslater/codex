"""Base view for metadata annotations."""
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateTimeField,
    F,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.fields import PositiveSmallIntegerField
from django.db.models.functions import Least, Lower, StrIndex, Substr

from codex.models import Comic, Folder, Imprint, Publisher, Series, Volume
from codex.views.browser.base import BrowserBaseView
from codex.views.browser.browser_order_by import BrowserOrderByView


class BrowserAnnotationsView(BrowserOrderByView):
    """Base class for views that need special metadata annotations."""

    _ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
    # used by browser & metadata
    GROUP_MODEL_MAP = {
        BrowserBaseView.ROOT_GROUP: None,
        "p": Publisher,
        "i": Imprint,
        "s": Series,
        "v": Volume,
        BrowserBaseView.COMIC_GROUP: Comic,
        BrowserBaseView.FOLDER_GROUP: Folder,
    }
    _NONE_DATETIMEFIELD = Value(None, DateTimeField())
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

    is_opds_1_acquisition = False

    def _annotate_search_score(self, queryset, is_model_comic, search_scores):
        """Annotate the search score for ordering by search score."""
        if self.order_key != "search_score":
            return queryset
        prefix = "comic__" if not is_model_comic else ""
        whens = []
        for pk, score in search_scores.items():
            when = {prefix + "pk": pk, "then": score}
            whens.append(When(**when))
        annotate = {prefix + "search_score": Case(*whens, default=0.0)}
        return queryset.annotate(**annotate)

    def _annotate_cover_pk(self, queryset, model):
        """Annotate the query set for the coverpath for the sort."""
        # Select comics for the children by an outer ref for annotation
        # Order the descendant comics by the sort argumentst
        if model == Comic:
            cover_pk = F("pk")
        else:
            # This creates two subqueries. It would be better condensed into one.
            # but there's no way to annotate an object or multiple values.
            cover_qs = queryset.filter(pk=OuterRef("pk"))
            cover_qs = self.add_order_by(cover_qs, model)
            cover_pk = Subquery(cover_qs.values("comic__pk")[:1])
        return queryset.annotate(cover_pk=cover_pk)

    @staticmethod
    def _annotate_page_count(qs, is_model_comic):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        if is_model_comic:
            return qs
        page_count_sum = Sum("comic__page_count", distinct=True)
        return qs.annotate(page_count=page_count_sum)

    @classmethod
    def _annotate_child_count(cls, qs, is_model_comic):
        """Annotate Child Count."""
        child_count_sum = (
            cls._ONE_INTEGERFIELD
            if is_model_comic
            else Count("comic__pk", distinct=True)
        )
        qs = qs.annotate(child_count=child_count_sum)
        if not is_model_comic:
            # XXX Extra filter for empty groups
            qs = qs.filter(child_count__gt=0)
        return qs

    def _annotate_bookmark_updated_at(self, qs, bm_rel, bm_filter):
        """Annotate bookmark_updated_at."""
        if not self.is_opds_1_acquisition and self.order_key != "bookmark_updated_at":
            return qs

        updated_at_rel = f"{bm_rel}__updated_at"
        bookmark_updated_at_aggregate = Min(
            updated_at_rel,
            default=self._NONE_DATETIMEFIELD,
            filter=bm_filter,
        )
        qs = qs.annotate(bookmark_updated_at=bookmark_updated_at_aggregate)

        if self.order_key == "bookmark_updated_at":
            # Special filter for this order key.
            qs = qs.exclude(bookmark_updated_at=None)

        return qs

    def _annotate_sort_name(self, queryset, model):
        """Sort groups by name ignoring articles."""
        if self.order_key != "sort_name":
            return queryset

        # first_space_index
        first_field = model.ORDERING[0]
        queryset = queryset.annotate(
            first_space_index=StrIndex(first_field, Value(" "))
        )

        # lowercase_first_word
        lowercase_first_word = Lower(
            Substr(first_field, 1, length=(F("first_space_index") - 1))  # type: ignore
        )
        queryset = queryset.annotate(
            lowercase_first_word=Case(
                When(Q(first_space_index__gt=0), then=lowercase_first_word)
            ),
            default=Value(""),
        )

        # sort_name
        return queryset.annotate(
            sort_name=Case(
                When(
                    lowercase_first_word__in=self._ARTICLES,
                    then=Substr(
                        first_field, F("first_space_index") + 1  # type: ignore
                    ),
                ),
                default=first_field,
            )
        )

    def _annotate_order_value(self, qs, model):
        """Annotate a main key for sorting."""
        order_func = self.get_order_value(model)
        return qs.annotate(order_value=order_func)

    def _annotate_bookmarks(self, qs, is_model_comic, bm_rel, bm_filter):
        """Hoist up bookmark annoations."""
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
                distinct=True,
            )

            finished_count = Sum(
                finished_rel,
                default=0,
                filter=bm_filter,
                output_field=PositiveSmallIntegerField(),
                distinct=True,
            )
            qs = qs.annotate(finished_count=finished_count)
            finished_aggregate = Case(
                When(
                    Q(finished_count=F("child_count")) | Q(page=F("page_count")),
                    then=True,
                ),
                When(page=0, then=False),
                default=None,
                output_field=BooleanField(),
            )

        return qs.annotate(
            page=bookmark_page,
            finished=finished_aggregate,
        )

    @staticmethod
    def _annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from bookmarks.
        # Requires page_count native to comic or aggregated
        # Least guard is for rare instances when bookmarks are set to
        # invalid high values
        then = Least(F("page") * 100.0 / F("page_count"), Value(100.0))
        progress = Case(When(page_count__gt=0, then=then), default=0.0)
        return queryset.annotate(progress=progress)

    def annotate_common_aggregates(self, qs, model, search_scores):
        """Annotate common aggregates between browser and metadata."""
        is_model_comic = model == Comic

        qs = self._annotate_search_score(qs, is_model_comic, search_scores)
        qs = self._annotate_child_count(qs, is_model_comic)
        qs = self._annotate_page_count(qs, is_model_comic)
        bm_rel = self.get_bm_rel(is_model_comic)
        bm_filter = self._get_my_bookmark_filter(bm_rel)
        qs = self._annotate_bookmark_updated_at(qs, bm_rel, bm_filter)
        qs = self._annotate_sort_name(qs, model)
        qs = self._annotate_order_value(qs, model)
        # cover depends on the above annotations for order-by
        qs = self._annotate_cover_pk(qs, model)
        qs = self._annotate_bookmarks(qs, is_model_comic, bm_rel, bm_filter)
        qs = self._annotate_progress(qs)
        return qs
