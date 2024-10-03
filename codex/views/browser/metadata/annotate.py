"""Metadata Annotations."""

from django.db.models import Count, IntegerField, Sum, Value

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.browser.annotate.card import BrowserAnnotateCardView

LOG = get_logger(__name__)
_ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS = frozenset({"path"})
_COMIC_VALUE_FIELDS_CONFLICTING = frozenset(
    {
        "created_at",
        "name",
        "path",
        "updated_at",
    }
)
_DISABLED_VALUE_FIELD_NAMES = frozenset(
    {"id", "pk", "sort_name", "stat"} | _COMIC_VALUE_FIELDS_CONFLICTING
)
_COMIC_VALUE_FIELD_NAMES = frozenset(
    # contains path
    field.name
    for field in Comic._meta.get_fields()
    if not field.is_relation and field.name not in _DISABLED_VALUE_FIELD_NAMES
)
_COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
_COMIC_RELATED_VALUE_FIELDS = frozenset({"series__volume_count", "volume__issue_count"})
_PATH_GROUPS = frozenset({"c", "f"})
_SUM_FIELDS = frozenset({"page_count", "size"})


class MetadataAnnotateView(BrowserAnnotateCardView):
    """Metadata Annotations."""

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = set(_COMIC_VALUE_FIELD_NAMES)
        group = self.kwargs["group"]
        if (
            not (self.is_admin and self.admin_flags["folder_view"])
            or group not in _PATH_GROUPS
        ):
            fields -= _ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
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

            if field in _SUM_FIELDS:
                val = Sum(full_field)
            else:
                # group_by makes the filter work, but prevents its
                # use as a subquery in the big query.
                sq = filtered_qs.alias(
                    filter_count=Count(full_field, distinct=True)
                ).filter(filter_count=1)
                sq = self.add_group_by(sq)
                sq = self.force_inner_joins(sq)
                sq = sq.values_list(full_field + related_suffix, flat=True)
                try:
                    val = sq[0]
                except IndexError:
                    val = None
                if field.endswith("count"):
                    output_field = IntegerField()
                else:
                    output_field = Comic._meta.get_field(field).__class__()
                val = Value(val, output_field)
            qs = qs.annotate(**{ann_field: val})

        return filtered_qs, qs

    def _annotate_values_and_fks(self, qs, filtered_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        querysets = (filtered_qs, qs)
        if qs.model is not Comic:
            comic_value_fields = self._get_comic_value_fields()
            querysets = self._intersection_annotate(querysets, comic_value_fields)

            # Conflicting Simple Values
            querysets = self._intersection_annotate(
                querysets,
                _COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=_COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        # Foreign Keys with special count values
        _, qs = self._intersection_annotate(
            querysets,
            _COMIC_RELATED_VALUE_FIELDS,
        )
        return qs
