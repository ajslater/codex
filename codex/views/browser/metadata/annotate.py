"""Metadata Annotations."""

from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.query import QuerySet

from codex.models import Comic
from codex.views.browser.annotate.card import BrowserAnnotateCardView
from codex.views.browser.metadata.const import (
    ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS,
    COMIC_RELATED_VALUE_FIELDS,
    COMIC_VALUE_FIELD_NAMES,
    COMIC_VALUE_FIELDS_CONFLICTING,
    COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
    PATH_GROUPS,
    SUM_FIELDS,
)


class MetadataAnnotateView(BrowserAnnotateCardView):
    """Metadata Annotations."""

    def _get_comic_value_fields(self) -> tuple:
        """Include the path field for staff."""
        fields = set(COMIC_VALUE_FIELD_NAMES)
        group = self.kwargs["group"]
        if (
            not (self.is_admin and self.admin_flags["folder_view"])
            or group not in PATH_GROUPS
        ):
            fields -= ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
        return tuple(fields)

    @staticmethod
    def _intersection_annotate_separate_sum_fields(
        fields,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Separate sum fields (direct aggregation expressions) from intersection fields (need distinct-count check)."""
        sum_fields = []
        intersection_fields = []
        for field in fields:
            if field in SUM_FIELDS:
                sum_fields.append(field)
            else:
                intersection_fields.append(field)
        return tuple(sum_fields), tuple(intersection_fields)

    def _intersection_annotate_count_sum_fields(
        self, sum_fields: tuple[str, ...], annotation_prefix: str, qs: QuerySet
    ) -> QuerySet:
        # Annotate sum fields directly as aggregate expressions.
        for field in sum_fields:
            ann_field = annotation_prefix + field.replace("__", "_")
            full_field = self.rel_prefix + field
            qs = qs.annotate(**{ann_field: Sum(full_field)})
        return qs

    def _intersection_annotate_count_intersection_fields(
        self, filtered_qs: QuerySet, intersection_fields: tuple[str, ...]
    ):
        """
        Batch query 1: Get distinct counts for ALL intersection fields at once.

        aggregate() collapses all rows into one result without
        GROUP BY, completely avoiding the group_by/subquery conflict.
        """
        count_base = self.force_inner_joins(filtered_qs)
        agg_kwargs = {}
        for field in intersection_fields:
            full_field = self.rel_prefix + field
            agg_kwargs[field] = Count(full_field, distinct=True)

        distinct_counts = count_base.aggregate(**agg_kwargs)

        # Keep only fields where all comics share exactly one distinct value.
        return tuple(f for f in intersection_fields if distinct_counts.get(f) == 1)

    def _intersection_annotate_fetch_intersecting_values(
        self,
        filtered_qs: QuerySet,
        related_suffix: str,
        single_value_fields: tuple[str, ...],
    ) -> tuple[str, ...]:
        """
        Batch query 2: Fetch the shared value for all qualifying fields in a single query.

        Since each field has exactly 1 distinct value, any row's value is representative.
        """
        value_base = self.force_inner_joins(filtered_qs)
        full_fields = tuple(
            self.rel_prefix + f + related_suffix for f in single_value_fields
        )
        return tuple(value_base.values_list(*full_fields).first())

    def _intersection_annotate(
        self,
        querysets,
        fields,
        related_suffix="",
        annotation_prefix="",
    ) -> tuple:
        """
        Annotate the intersection of value and fk fields.

        For each field, check if all comics in the filtered queryset share
        exactly one distinct value. If so, annotate that value as a constant.

        Uses aggregate() to batch all distinct-count checks into a single
        query, then fetches all single-valued fields in one more query.
        This replaces the previous approach of 2 queries per field.
        """
        (filtered_qs, qs) = querysets
        sum_fields, intersection_fields = (
            self._intersection_annotate_separate_sum_fields(fields)
        )
        qs = self._intersection_annotate_count_sum_fields(
            sum_fields, annotation_prefix, qs
        )
        if not intersection_fields:
            return filtered_qs, qs

        single_value_fields = self._intersection_annotate_count_intersection_fields(
            filtered_qs, intersection_fields
        )
        if not single_value_fields:
            return filtered_qs, qs

        row = self._intersection_annotate_fetch_intersecting_values(
            filtered_qs, related_suffix, single_value_fields
        )
        if not row:
            return filtered_qs, qs

        # Annotate each single-value field as a Value constant.
        for field, val in zip(single_value_fields, row, strict=True):
            ann_field = annotation_prefix + field.replace("__", "_")
            if field.endswith("count"):
                output_field = IntegerField()
            else:
                output_field = Comic._meta.get_field(field)
            qs = qs.annotate(**{ann_field: Value(val, output_field)})

        return filtered_qs, qs

    def annotate_values_and_fks(self, qs, filtered_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        querysets = (filtered_qs, qs)
        if qs.model is not Comic:
            comic_value_fields = self._get_comic_value_fields()
            querysets = self._intersection_annotate(querysets, comic_value_fields)

            # Conflicting Simple Values
            querysets = self._intersection_annotate(
                querysets,
                COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        # Foreign Keys with special count values
        _, qs = self._intersection_annotate(
            querysets,
            COMIC_RELATED_VALUE_FIELDS,
        )
        return qs
