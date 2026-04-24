"""Aggregate Group and Comic Metadata View."""

from typing import Any, override

from django.db.models import QuerySet, Sum
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.choices.admin import AdminFlagChoices
from codex.serializers.browser.metadata import MetadataSerializer
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.views.browser.metadata.const import SUM_FIELDS
from codex.views.browser.metadata.copy_intersections import (
    MetadataCopyIntersectionsView,
)


class MetadataView(MetadataCopyIntersectionsView):
    """Aggregate Group and Comic Metadata View."""

    serializer_class: type[BaseSerializer] | None = MetadataSerializer
    input_serializer_class: type[BrowserFilterChoicesInputSerializer] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        BrowserFilterChoicesInputSerializer
    )
    TARGET: str = "metadata"
    ADMIN_FLAGS = (AdminFlagChoices.FOLDER_VIEW,)

    @override
    def _get_valid_browse_nav_groups(self, valid_top_groups) -> tuple:
        """Limited allowed nav groups for metadata."""
        # Overrides method in browser.validate
        group = self.kwargs["group"]
        return (group,)

    def _raise_not_found(self, exc=None) -> None:
        """Raise an exception if the object is not found."""
        pks = self.kwargs["pks"]
        group = self.kwargs["group"]
        detail = f"Filtered metadata for {group}/{pks} not found"
        raise NotFound(detail=detail) from exc

    def _get_first_object(self, qs: QuerySet):
        obj = qs[0]
        if not obj:
            reason = "Empty obj"
            raise ValueError(reason)
        return obj

    def _aggregate_multi_pk_sums(self, filtered_qs, obj):
        """
        Aggregate sum fields across multiple selected items.

        When multiple pks are selected for any group model, qs[0]
        only returns the first item's values. This method computes
        the correct sums across all selected items using rel_prefix
        to traverse from the group model to the Comic fields.
        """
        aggs = {}
        for field in SUM_FIELDS:
            full_field = self.rel_prefix + field
            aggs[field] = Sum(full_field)
        sums = self.force_inner_joins(filtered_qs).aggregate(**aggs)
        for field, value in sums.items():
            if value is not None:
                setattr(obj, field, value)
        return obj

    @override
    def get_object(self) -> Any:
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.

        qs = self.get_filtered_queryset(self.model)
        filtered_qs = qs

        # Annotate
        qs = self.annotate_order_aggregates(qs)
        qs = self.annotate_card_aggregates(qs)
        qs = self.annotate_cover(qs)
        qs = self.annotate_values_and_fks(qs, filtered_qs)
        qs = self.add_group_by(qs)
        qs = self.force_inner_joins(qs)

        # Get Object
        try:
            obj = self._get_first_object(qs)
        except (IndexError, ValueError) as exc:
            return self._raise_not_found(exc)

        # Aggregate sum fields for multi-pk selections
        pks = self.kwargs.get("pks", ())
        if len(pks) > 1:
            obj = self._aggregate_multi_pk_sums(filtered_qs, obj)

        # Hacks to add to object after query
        groups, fk_intersections, m2m_intersections = self.query_intersections(
            filtered_qs
        )
        return self.copy_intersections_into_comic_fields(
            obj, groups, fk_intersections, m2m_intersections
        )

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs) -> Response:
        """Get metadata for a filtered browse group."""
        # Init
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Exception:
            logger.exception(f"Getting metadata {self.kwargs}")
            raise
