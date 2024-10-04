"""Aggregate Group and Comic Metadata View."""

from types import MappingProxyType

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.serializers.browser.metadata import MetadataSerializer
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerilalizer
from codex.views.browser.metadata.copy_intersections import (
    MetadataCopyIntersectionsView,
)

LOG = get_logger(__name__)


class MetadataView(MetadataCopyIntersectionsView):
    """Aggregate Group and Comic Metadata View."""

    serializer_class = MetadataSerializer
    input_serializer_class = BrowserFilterChoicesInputSerilalizer
    TARGET = "metadata"
    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
        }
    )

    def _get_valid_browse_nav_groups(self, valid_top_groups):  # noqa: ARG002
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
        qs = self._annotate_values_and_fks(qs, filtered_qs)
        qs = self.add_group_by(qs)
        qs = self.force_inner_joins(qs)

        # Get Object
        try:
            obj = qs[0]
            if not obj:
                reason = "Empty obj"
                raise ValueError(reason)  # noqa TRY301
        except (IndexError, ValueError) as exc:
            return self._raise_not_found(exc)

        # Hacks to add to object after query
        groups, m2m_intersections = self.query_intersections(filtered_qs)
        return self.copy_intersections_into_comic_fields(obj, groups, m2m_intersections)

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Exception:
            LOG.exception(f"Getting metadata {self.kwargs}")
