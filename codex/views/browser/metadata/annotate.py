"""Metadata Annotations."""

from django.db.models import Count, IntegerField, Sum, Value

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

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = set(COMIC_VALUE_FIELD_NAMES)
        group = self.kwargs["group"]
        if (
            not (self.is_admin and self.admin_flags["folder_view"])
            or group not in PATH_GROUPS
        ):
            fields -= ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
        return tuple(fields)

    def _intersection_annotate(
        self,
        querysets,
        fields,
        related_suffix="",
        annotation_prefix="",
    ):
        """Annotate the intersection of value and fk fields."""
        (filtered_qs, qs) = querysets

        for field in fields:
            # Annotate variant counts
            # If 1 variant, annotate value, otherwise None
            ann_field = annotation_prefix + field.replace("__", "_")

            full_field = self.rel_prefix + field

            if field in SUM_FIELDS:
                val = Sum(full_field)
            else:
                # group_by makes the filter work, but prevents its
                # use as a subquery in the big query.
                sq = filtered_qs.annotate(filter_count=Count(full_field, distinct=True))
                sq = sq.filter(filter_count=1)
                sq = self.add_group_by(sq)
                sq = self.force_inner_joins(sq)
                if not sq.count():
                    continue
                sq = sq.values_list(full_field + related_suffix, flat=True)
                try:
                    val = sq[0]
                except IndexError:
                    continue
                if field.endswith("count"):
                    output_field = IntegerField()
                else:
                    output_field = Comic._meta.get_field(field)
                val = Value(val, output_field)
            qs = qs.annotate(**{ann_field: val})

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
