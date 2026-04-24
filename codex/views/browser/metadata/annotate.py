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
    def _partition_sum_fields(
        fields,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Separate direct-aggregation SUM fields from distinct-count intersection fields."""
        sum_fields = []
        intersection_fields = []
        for field in fields:
            if field in SUM_FIELDS:
                sum_fields.append(field)
            else:
                intersection_fields.append(field)
        return tuple(sum_fields), tuple(intersection_fields)

    def _annotate_sum_fields(self, qs: QuerySet, sum_field_specs) -> QuerySet:
        """Annotate SUM aggregate expressions on qs."""
        for field, prefix in sum_field_specs:
            ann_field = prefix + field.replace("__", "_")
            full_field = self.rel_prefix + field
            qs = qs.annotate(**{ann_field: Sum(full_field)})
        return qs

    def _aggregate_distinct_counts(
        self, filtered_qs: QuerySet, intersection_field_specs
    ) -> list:
        """Batch distinct-count aggregate across all intersection fields; return single-valued specs."""
        if not intersection_field_specs:
            return []
        count_base = self.force_inner_joins(filtered_qs)
        agg_kwargs = {}
        keys = []
        for field, _ in intersection_field_specs:
            key = f"_ann{len(keys)}"
            agg_kwargs[key] = Count(self.rel_prefix + field, distinct=True)
            keys.append(key)
        distinct_counts = count_base.aggregate(**agg_kwargs)
        return [
            intersection_field_specs[i]
            for i, key in enumerate(keys)
            if distinct_counts.get(key) == 1
        ]

    def _fetch_intersecting_values(
        self, filtered_qs: QuerySet, single_value_specs
    ) -> tuple:
        """Batch values_list across all single-valued intersection fields."""
        value_base = self.force_inner_joins(filtered_qs)
        full_fields = tuple(self.rel_prefix + field for field, _ in single_value_specs)
        row = value_base.values_list(*full_fields).first()
        return row or ()

    @staticmethod
    def _value_output_field(field: str):
        if field.endswith("count"):
            return IntegerField()
        return Comic._meta.get_field(field)

    def _annotate_value_constants(
        self, qs: QuerySet, single_value_specs, row
    ) -> QuerySet:
        """Annotate each single-valued field as a constant expression."""
        for (field, prefix), val in zip(single_value_specs, row, strict=True):
            ann_field = prefix + field.replace("__", "_")
            qs = qs.annotate(**{ann_field: Value(val, self._value_output_field(field))})
        return qs

    def _intersection_annotate(self, querysets, field_groups) -> tuple:
        """
        Annotate the intersection of value / fk fields across multiple groups.

        field_groups: iterable of ``(fields, annotation_prefix)`` tuples. Each
        group's fields are partitioned into SUM aggregations (direct) and
        intersection fields (distinct-count check). All intersection fields
        across all groups are collapsed into ONE ``aggregate()`` query and ONE
        ``values_list()`` query, regardless of group count.
        """
        filtered_qs, qs = querysets

        sum_field_specs = []
        intersection_field_specs = []
        for fields, annotation_prefix in field_groups:
            sum_f, int_f = self._partition_sum_fields(fields)
            sum_field_specs.extend((f, annotation_prefix) for f in sum_f)
            intersection_field_specs.extend((f, annotation_prefix) for f in int_f)

        qs = self._annotate_sum_fields(qs, sum_field_specs)

        single_value_specs = self._aggregate_distinct_counts(
            filtered_qs, intersection_field_specs
        )
        if not single_value_specs:
            return filtered_qs, qs

        row = self._fetch_intersecting_values(filtered_qs, single_value_specs)
        if not row:
            return filtered_qs, qs

        qs = self._annotate_value_constants(qs, single_value_specs, row)
        return filtered_qs, qs

    def annotate_values_and_fks(self, qs, filtered_qs):
        """Annotate comic values and comic foreign key values."""
        field_groups = []
        if qs.model is not Comic:
            field_groups.append((self._get_comic_value_fields(), ""))
            field_groups.append(
                (
                    COMIC_VALUE_FIELDS_CONFLICTING,
                    COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
                )
            )
        field_groups.append((COMIC_RELATED_VALUE_FIELDS, ""))

        _, qs = self._intersection_annotate((filtered_qs, qs), field_groups)
        return qs
