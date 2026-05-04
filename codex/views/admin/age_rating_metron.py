"""
Admin read-only AgeRatingMetron list.

Serves the fully-seeded canonical :class:`AgeRatingMetron` lookup table to
admin dialogs (e.g. the per-user age-rating dropdown). The table never
grows or shrinks at runtime, so only read endpoints are exposed.
"""

from codex.models.age_rating import AgeRatingMetron
from codex.serializers.models.named import AgeRatingMetronSerializer
from codex.views.admin.auth import AdminReadOnlyModelViewSet


class AdminAgeRatingMetronViewSet(AdminReadOnlyModelViewSet):
    """Admin Read-Only AgeRatingMetron viewset."""

    # Don't return "Unknown" value
    queryset = AgeRatingMetron.objects.filter(index__gte=0).order_by("index")
    serializer_class = AgeRatingMetronSerializer
