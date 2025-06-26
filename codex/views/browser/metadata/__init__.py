"""Aggregate Group and Comic Metadata View."""

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.serializers.browser.metadata import MetadataSerializer
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
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
    def _get_valid_browse_nav_groups(self, valid_top_groups):
        """Limited allowed nav groups for metadata."""
        # Overrides method in browser.validate
        group = self.kwargs["group"]
        return (group,)

    def _raise_not_found(self, exc=None):
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

    @override
    def get_object(self):
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.

        qs = self.get_filtered_queryset(self.model)
        filtered_qs = qs

        # Annotate
        qs = self.annotate_order_aggregates(qs)
        qs = self.annotate_card_aggregates(qs)
        qs = self.annotate_values_and_fks(qs, filtered_qs)
        qs = self.add_group_by(qs)
        qs = self.force_inner_joins(qs)

        # Get Object
        try:
            obj = self._get_first_object(qs)
        except (IndexError, ValueError) as exc:
            return self._raise_not_found(exc)

        # Hacks to add to object after query
        groups, fk_intersections, m2m_intersections = self.query_intersections(
            filtered_qs
        )
        return self.copy_intersections_into_comic_fields(
            obj, groups, fk_intersections, m2m_intersections
        )

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Exception:
            logger.exception(f"Getting metadata {self.kwargs}")
