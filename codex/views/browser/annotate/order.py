"""Base view for metadata annotations."""

from os import sep
from types import MappingProxyType

from django.db.models import (
    F,
    FilteredRelation,
    Q,
    QuerySet,
    Value,
)
from django.db.models.aggregates import Avg, Count, Max, Min, Sum
from django.db.models.fields import CharField
from django.db.models.functions import Reverse, Right, StrIndex

from codex.choices.browser import BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS
from codex.models import (
    Comic,
    Folder,
    StoryArc,
)
from codex.models.functions import ComicFTSRank, JsonGroupArray
from codex.models.groups import Volume
from codex.views.browser.columns import m2m_alias_for, m2m_columns
from codex.views.browser.intersections import (
    m2m_intersection_sort_expr,
    scalar_intersection_sort_expr,
)
from codex.views.browser.order_by import (
    BrowserOrderByView,
    comic_order_path,
)
from codex.views.const import (
    NONE_INTEGERFIELD,
    STORY_ARC_GROUP,
)
from codex.views.mixins import SharedAnnotationsMixin

_ORDER_AGGREGATE_FUNCS = MappingProxyType(
    # These are annotated to order_value because they're simple relations.
    # ``Min`` is a sentinel for "use the directional aggregate" — see
    # ``annotate_order_value``: forward-sort uses Min, reverse uses Max.
    # ``Avg`` and ``Sum`` are kept as configured regardless of direction.
    {
        "age_rating": Avg,
        "child_count": Min,
        "country": Min,
        "created_at": Min,
        "critical_rating": Avg,
        "date": Min,
        "day": Min,
        "file_type": Min,
        "imprint_name": Min,
        # ``issue`` is virtual: its order_value annotation aggregates
        # the underlying ``issue_number`` field (resolved via
        # ``comic_order_path``). Group rows therefore sort by their
        # min/max child issue number; the suffix secondary applies
        # only to Comic-row ORDER BY.
        "issue": Min,
        "language": Min,
        "main_character": Min,
        "main_team": Min,
        "metadata_mtime": Min,
        "monochrome": Min,
        "month": Min,
        "original_format": Min,
        "page_count": Sum,
        "publisher_name": Min,
        "reading_direction": Min,
        "scan_info": Min,
        "series_name": Min,
        "size": Sum,
        "tagger": Min,
        "updated_at": Min,
        "volume_name": Min,
        "year": Min,
    }
)
_ANNOTATED_ORDER_FIELDS = frozenset(
    # These are annotated with their own functions
    {
        "bookmark_updated_at",
        "child_count",
        "filename",
        "search_score",
        "sort_name",
        "story_arc_number",
    }
)


class BrowserAnnotateOrderView(BrowserOrderByView, SharedAnnotationsMixin):
    """Base class for views that need special metadata annotations."""

    CARD_TARGETS = frozenset({"browser", "metadata"})
    _OPDS_TARGETS = frozenset({"opds1", "opds2"})
    _PAGE_COUNT_TARGETS = frozenset(CARD_TARGETS | _OPDS_TARGETS)
    _COVER_AND_CARD_TARGETS = frozenset(CARD_TARGETS | {"cover"})

    def __init__(self, *args, **kwargs) -> None:
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._order_agg_func: type[Min | Max] | None = None
        self._is_opds_acquisition: bool | None = None
        self._opds_acquisition_groups: frozenset[str] | None = None
        self.bmua_is_max = False
        self._child_count_annotated = False

    @property
    def opds_acquisition_groups(self):
        """Memoize the opds acquisition groups."""
        if self._opds_acquisition_groups is None:
            groups = {"a", "f", "c"}
            groups |= {*self.valid_nav_groups[-2:]}
            self._opds_acquisition_groups = frozenset(groups)
        return self._opds_acquisition_groups

    @property
    def is_opds_acquisition(self) -> bool:
        """Memoize if we're in an opds acquisition view."""
        if self._is_opds_acquisition is None:
            is_opds_acquisition = self.TARGET in self._OPDS_TARGETS
            if is_opds_acquisition:
                group = self.kwargs.get("group")
                is_opds_acquisition &= group in self.opds_acquisition_groups
                if is_opds_acquisition and group == "a":
                    pks = self.kwargs["pks"]
                    is_opds_acquisition &= bool(pks and 0 not in pks)
            self._is_opds_acquisition = is_opds_acquisition
        return self._is_opds_acquisition

    @property
    def order_agg_func(self):
        """Get the order aggregate function."""
        if self._order_agg_func is None:
            order_reverse = self.params.get("order_reverse")
            self._order_agg_func = Max if order_reverse else Min
        return self._order_agg_func

    def _alias_sort_names(self, qs):
        """Annotate sort_name."""
        if self.order_key != "sort_name" and not (
            qs.model is StoryArc and self.order_key == "story_arc_number"
        ):
            return qs
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        show = MappingProxyType(self.params["show"])
        sort_name_annotations = self.get_sort_name_annotations(
            qs.model, group, pks, show
        )
        if sort_name_annotations:
            qs = qs.alias(**sort_name_annotations)
            if qs.model is Comic:
                self._comic_sort_names = tuple(sort_name_annotations.keys())
        return qs

    def get_filename_func(self, model) -> Right:
        """Get the filename creation function."""
        prefix = "" if model == Comic else self.rel_prefix
        path_rel = prefix + "path"

        return Right(
            path_rel,
            StrIndex(  # pyright: ignore[reportArgumentType],# ty: ignore[invalid-argument-type]
                Reverse(F(path_rel)),
                Value(sep),
            )
            - 1,
            output_field=CharField(),
        )

    def _alias_filename(self, qs):
        """Calculate filename from path in the db."""
        if self.order_key != "filename":
            return qs
        if qs.model is Folder:
            filename = F("name")
        else:
            filename_func = self.get_filename_func(qs.model)
            filename = self.order_agg_func(filename_func)
        return qs.alias(filename=filename)

    def _alias_story_arc_number(self, qs):
        if self.order_key != "story_arc_number":
            return qs

        # Get story_arc__pk
        group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        if group == STORY_ARC_GROUP and pks:
            story_arc_pks = pks
        else:
            story_arc_pks = self.params.get("filters", {}).get("story_arcs", ())

        # If we have one annotate it.
        if story_arc_pks:
            rel = self.get_rel_prefix(qs.model) + "story_arc_numbers"
            condition_rel = "pk" if qs.model is StoryArc else rel + "__story_arc"
            condition = Q(**{f"{condition_rel}__in": story_arc_pks})
            qs = qs.alias(
                selected_story_arc_number=FilteredRelation(rel, condition=condition),
            )
            story_arc_number = self.order_agg_func("selected_story_arc_number__number")
        else:
            story_arc_number = NONE_INTEGERFIELD

        return qs.alias(story_arc_number=story_arc_number)

    def _annotate_page_count(self, qs):
        """Hoist up total page_count of children."""
        # Used for sorting and progress
        if qs.model is Comic or (
            self.order_key != "page_count"
            and self.TARGET not in self._PAGE_COUNT_TARGETS
        ):
            return qs

        rel = self.rel_prefix + "page_count"
        page_count_sum = Sum(rel, distinct=True)
        if self.TARGET == "browser":
            qs = qs.alias(page_count=page_count_sum)
        else:
            qs = qs.annotate(page_count=page_count_sum)
        return qs

    def _annotate_bookmark_updated_at(self, qs) -> QuerySet:
        if self.is_opds_acquisition or self.order_key == "bookmark_updated_at":
            bmua_agg = self.get_max_bookmark_updated_at_aggregate(
                qs.model, agg_func=self.order_agg_func
            )
            # `self.bmua_is_max` is read by `annotate.bookmark` to skip a
            # second aggregate, and by the serializer to compute mtime.
            self.bmua_is_max = self.order_agg_func is Max
            qs = qs.annotate(bookmark_updated_at=bmua_agg)
        return qs

    def _annotate_search_scores(self, qs, *, for_cover: bool = False):
        """Annotate Search Scores."""
        if (
            self.TARGET not in self._COVER_AND_CARD_TARGETS
            or self.order_key != "search_score"
        ):
            return qs

        qs = qs.annotate(search_score=ComicFTSRank())
        # ``group_by`` dedupes rows that join long relations (e.g.
        # story_arc) from the outer browse query. The cover subquery is
        # already ``.distinct() ... LIMIT 1`` and the custom force-group-by
        # emits a literal ``"codex_comic"."id"`` that does not survive the
        # nested-subquery aliasing — skip it in the cover path.
        if for_cover:
            return qs
        # Skip ``group_by("id")`` on Comic queries that don't actually fan out
        # via an m2m join — there's nothing to dedupe and the GROUP BY just
        # forces SQLite to materialize an unnecessary aggregate. Non-Comic
        # queries traverse ``comic__`` (one-to-many) for ACL/group filters
        # and always need the dedupe.
        if qs.model is not Comic or self.comic_filter_uses_m2m:
            qs = qs.group_by("id")
        return qs

    def annotate_child_count(self, qs):
        """Annotate child count."""
        if qs.model is Comic or self._child_count_annotated:
            return qs
        rel = self.rel_prefix + "pk"
        count_func = Count(rel, distinct=True)
        ann = {"child_count": count_func}
        qs = qs.alias(**ann) if self.TARGET == "opds2" else qs.annotate(**ann)
        self._child_count_annotated = True
        return qs

    def _annotate_order_child_count(self, qs):
        """Annotate child count for order."""
        if self.order_key != "child_count":
            return qs
        return self.annotate_child_count(qs)

    def _comic_order_value(self):
        """Comic-row order_value: direct field or M2M alias."""
        if self.order_key in m2m_columns():
            return F(m2m_alias_for(self.order_key))
        order_key = "sort_name" if self.order_key == "child_count" else self.order_key
        return F(comic_order_path(order_key))

    def _group_m2m_order_value(self, qs):
        """Group-row M2M order_value, falling back to ``sort_name``."""
        isort_expr = m2m_intersection_sort_expr(qs.model, self.order_key)
        if isort_expr is not None:
            return qs, isort_expr
        if qs.model is Volume:
            qs = qs.alias(sort_name=F("name"))
        return qs, F("sort_name")

    def _group_scalar_order_value(self, qs):
        """Group-row scalar / FK-name order_value (intersection-aware)."""
        # Display uses intersection — a value renders only when every
        # child comic agrees — so the sort key matches that rule.
        # Falls back to the legacy aggregate path when the column /
        # group model isn't wired so adding a new registry scalar
        # doesn't silently regress its sort.
        isort_expr = scalar_intersection_sort_expr(qs.model, self.order_key)
        if isort_expr is not None:
            return isort_expr
        agg_func = _ORDER_AGGREGATE_FUNCS[self.order_key]
        agg_func = self.order_agg_func if agg_func == Min else agg_func
        field = self.rel_prefix + comic_order_path(self.order_key)
        return agg_func(field)

    def annotate_order_value(self, qs):
        """Annotate a main key for sorting and browser card display."""
        if self.TARGET == "metadata":
            return qs
        if qs.model is Folder and self.order_key == "filename":
            order_value = F("name")
        elif qs.model is Comic:
            order_value = self._comic_order_value()
        elif self.order_key in m2m_columns():
            qs, order_value = self._group_m2m_order_value(qs)
        elif self.order_key in _ANNOTATED_ORDER_FIELDS:
            order_value = F(self.order_key)
        else:
            order_value = self._group_scalar_order_value(qs)

        if self.TARGET == "browser":
            qs = qs.annotate(order_value=order_value)
        else:
            qs = qs.alias(order_value=order_value)
        return qs

    def annotate_comic_extra_specials(self, qs):
        """
        Annotate Comic-row aliases the multi-sort tail needs.

        Comic queries route their multi-sort tail through
        ``_add_comic_order_by`` (which returns field / alias names),
        not through ``_extra_order_value_expr``. So when an extra
        references ``bookmark_updated_at`` or ``filename`` the
        underlying alias has to exist on the queryset for
        ``ORDER BY`` to resolve. The primary's ``_annotate_*`` /
        ``_alias_*`` helpers gate on ``self.order_key`` and skip when
        these keys appear only as extras; this method lazily annotates
        them in that case. Direction-agnostic (``Max`` aggregate) —
        the per-extra ``reverse`` flag is applied as the SQL prefix
        in ``_add_extra_order_by``.
        """
        if qs.model is not Comic or self.params.get("view_mode") != "table":
            return qs
        extras = self.params.get("order_extra_keys") or ()
        keys = {entry.get("key") for entry in extras if entry.get("key")}
        if "bookmark_updated_at" in keys and self.order_key != "bookmark_updated_at":
            # Comic has at most one bookmark row per user, so the
            # aggregate is direction-equivalent.
            qs = qs.annotate(
                bookmark_updated_at=self.get_max_bookmark_updated_at_aggregate(
                    Comic, agg_func=Max
                )
            )
        if "filename" in keys and self.order_key != "filename":
            qs = qs.alias(filename=self.get_filename_func(Comic))
        return qs

    def _extra_group_special(self, qs, key: str, *, reverse: bool):
        """Group-row extra: hand-rolled cases (returns None when not special)."""
        if key == "sort_name":
            return F("sort_name")
        if key == "child_count":
            return Count(self.rel_prefix + "pk", distinct=True)
        if key == "filename":
            if qs.model is Folder:
                return F("name")
            agg = Max if reverse else Min
            return agg(self.get_filename_func(qs.model))
        if key == "bookmark_updated_at":
            agg = Max if reverse else Min
            return self.get_max_bookmark_updated_at_aggregate(qs.model, agg_func=agg)
        return None

    def _extra_group_expr(self, qs, key: str, *, reverse: bool):
        """Group-row extra: aggregate, intersection, or direct field."""
        if key in BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS:
            return None
        if key in m2m_columns():
            return m2m_intersection_sort_expr(qs.model, key)
        special = self._extra_group_special(qs, key, reverse=reverse)
        if special is not None:
            return special
        # Match the primary's intersection-aware sort for scalars /
        # FK-names so the shift-click extra ranks rows by the same
        # rule the cell display uses.
        isort_expr = scalar_intersection_sort_expr(qs.model, key)
        if isort_expr is not None:
            return isort_expr
        agg_func = _ORDER_AGGREGATE_FUNCS.get(key)
        if agg_func is None:
            return None
        # ``Min`` is the "directional" sentinel. Each extra carries
        # its own ``reverse`` so the agg has to be picked per-entry
        # instead of pulling from ``self.order_agg_func`` (that one
        # is for the primary).
        if agg_func is Min:
            agg_func = Max if reverse else Min
        return agg_func(self.rel_prefix + comic_order_path(key))

    def annotate_extra_order_values(self, qs):
        """
        Annotate per-extra ``order_value`` aliases on group querysets.

        Comic queries don't go through this path — their multi-sort
        tail references direct Comic fields, M2M aliases annotated
        by ``_add_table_view_sort_annotations``, or
        ``bookmark_updated_at`` / ``filename`` aliases annotated by
        ``annotate_comic_extra_specials``. Group querysets need a
        parallel ``_table_extra_value_<idx>`` annotation per extra
        so the ORDER BY tail can reference an aggregated child-comic
        value. Skipped outside table-view mode so cover requests
        don't carry these aliases unnecessarily.
        """
        if (
            self.TARGET == "metadata"
            or qs.model is Comic
            or self.params.get("view_mode") != "table"
        ):
            return qs
        extras = self.params.get("order_extra_keys") or ()
        if not extras:
            return qs
        annotations: dict = {}
        for idx, entry in enumerate(extras):
            key = entry.get("key")
            if not key:
                continue
            expr = self._extra_group_expr(qs, key, reverse=bool(entry.get("reverse")))
            if expr is None:
                # Unsupported (e.g. M2M without an intersection
                # expression for this group model, or an
                # annotated-only key without bespoke extra wiring)
                # — fall back to ``sort_name`` so the alias still
                # binds and the ORDER BY emitted in
                # :func:`_add_extra_order_by` doesn't reference a
                # missing column.
                expr = F("sort_name")
            annotations[self.extra_order_value_alias(idx)] = expr
        if annotations:
            if self.TARGET == "browser":
                qs = qs.annotate(**annotations)
            else:
                qs = qs.alias(**annotations)
        return qs

    def annotate_order_aggregates(self, qs: QuerySet, *, for_cover: bool = False):
        """Annotate common aggregates between browser and metadata."""
        # ``for_cover`` is a pipeline-trim. The cover path needs ORDER BY to
        # pick the "first" comic, but it never reads ``ids`` or ``page_count``
        # — dropping those removes a JsonGroupArray aggregate and a Sum per
        # call. Applied inside the cover fan-out and inside the cover_pk
        # subquery on BrowserView card annotation.
        if not for_cover:
            qs = qs.annotate(ids=JsonGroupArray("id", distinct=True, order_by="id"))
        qs = self._annotate_search_scores(qs, for_cover=for_cover)
        qs = self._alias_sort_names(qs)
        qs = self._alias_filename(qs)
        qs = self._alias_story_arc_number(qs)
        if not for_cover:
            qs = self._annotate_page_count(qs)
        qs = self._annotate_bookmark_updated_at(qs)
        qs = self._annotate_order_child_count(qs)
        if qs.model is not Comic:
            # comic orders on indexed fields when it can
            qs = self.annotate_order_value(qs)
            if not for_cover:
                qs = self.annotate_extra_order_values(qs)
        elif not for_cover:
            qs = self.annotate_comic_extra_specials(qs)
        return qs
