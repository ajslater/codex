"""Base view for metadata annotations."""

from os.path import sep

from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DateTimeField,
    F,
    FilteredRelation,
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

from codex.models import Comic
from codex.views.browser.browser_order_by import BrowserOrderByView


class BrowserAnnotationsView(BrowserOrderByView):
    """Base class for views that need special metadata annotations."""

    _ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())
    _NONE_INTEGERFIELD = Value(None, PositiveSmallIntegerField())
    _NONE_DATETIMEFIELD = Value(None, DateTimeField())
    _ARTICLES = frozenset(
        ("a", "an", "the")  # en    # noqa RUF005
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

    def _annotate_search_score(self, queryset, search_scores, model):
        """Annotate the search score for ordering by search score.

        Choose the maximum matching score for the group.
        """
        if self.order_key != "search_score":
            return queryset
        whens = []
        prefix = "" if model == Comic else self.rel_prefix
        for pk, score in search_scores.items():
            when = {prefix + "pk": pk, "then": score}
            whens.append(When(**when))
        annotate = {"search_score": Max(Case(*whens, default=0.0))}
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
            cover_qs = self.add_order_by(cover_qs, model, True)
            cover_pk = Subquery(cover_qs.values(self.rel_prefix + "pk")[:1])
        return queryset.annotate(cover_pk=cover_pk)

    def _annotate_page_count(self, qs, model):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        if model == Comic:
            return qs

        page_count_sum = Sum(self.rel_prefix + "page_count", distinct=True)
        return qs.annotate(page_count=page_count_sum)

    def _annotate_child_count(self, qs, model):
        """Annotate Child Count."""
        self.kwargs.get("group")
        if model == Comic:
            child_count_sum = self._ONE_INTEGERFIELD
        else:
            child_count_sum = Count(self.rel_prefix + "pk", distinct=True)
        qs = qs.annotate(child_count=child_count_sum)
        if model != Comic:
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
        return qs.annotate(bookmark_updated_at=bookmark_updated_at_aggregate)

    def _annotate_sort_name(self, queryset, model):
        """Sort groups by name ignoring articles."""
        if self.order_key != "sort_name":
            return queryset

        if self.kwargs.get("group") == self.FOLDER_GROUP and model == Comic:
            # File View Filename
            return queryset.annotate(
                sort_name=Right(
                    "path",
                    StrIndex(Reverse(F("path")), Value(sep)) - 1,  # type: ignore
                    output_field=CharField(),
                )
            )

        ##################################################
        # Otherwise Remove articles from the browse name #
        ##################################################

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
                        first_field,
                        F("first_space_index") + 1,  # type: ignore
                    ),
                ),
                default=first_field,
            )
        )

    def _annotate_story_arc_number(self, qs):
        if self.order_key != "story_arc_number":
            return qs

        # Get story_arc__pk
        group = self.kwargs["group"]
        pk = self.kwargs["pk"]
        if group == self.STORY_ARC_GROUP and pk:
            story_arc_pk = pk
        elif story_arc_pks := self.params.get("filters", {}).get(  # type: ignore
            "story_arcs", []
        ):
            story_arc_pk = story_arc_pks[0]
        else:
            story_arc_pk = None

        # If we have one annotate it.
        if story_arc_pk:
            san_rel = self.rel_prefix + "story_arc_numbers"
            rel = f"{san_rel}"
            condition = Q(**{f"{san_rel}__story_arc": story_arc_pk})
            qs = qs.annotate(
                selected_story_arc_number=FilteredRelation(rel, condition=condition),
                story_arc_number=F("selected_story_arc_number__number"),
            )
        else:
            qs = qs.annotate(story_arc_number=self._NONE_INTEGERFIELD)
        return qs

    def _annotate_order_value(self, qs, model):
        """Annotate a main key for sorting."""
        order_func = self.get_order_value(model)
        return qs.annotate(order_value=order_func)

    def _annotate_bookmarks(self, qs, model, bm_rel, bm_filter):
        """Hoist up bookmark annotations."""
        page_rel = f"{bm_rel}__page"
        finished_rel = f"{bm_rel}__finished"

        if model == Comic:
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
                    When(**{finished_rel: True}, then=f"{self.rel_prefix}page_count"),
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

    @staticmethod
    def _annotate_mtime(queryset):
        return queryset.annotate(mtime=Max("updated_at"))

    def annotate_common_aggregates(self, qs, model, search_scores):
        """Annotate common aggregates between browser and metadata."""
        qs = self._annotate_search_score(qs, search_scores, model)
        qs = self._annotate_child_count(qs, model)
        qs = self._annotate_page_count(qs, model)
        bm_rel = self.get_bm_rel(model)
        bm_filter = self._get_my_bookmark_filter(bm_rel)
        qs = self._annotate_bookmark_updated_at(qs, bm_rel, bm_filter)
        qs = self._annotate_sort_name(qs, model)
        qs = self._annotate_story_arc_number(qs)
        qs = self._annotate_order_value(qs, model)
        # cover depends on the above annotations for order-by
        qs = self._annotate_cover_pk(qs, model)
        qs = self._annotate_bookmarks(qs, model, bm_rel, bm_filter)
        qs = self._annotate_mtime(qs)
        return self._annotate_progress(qs)
