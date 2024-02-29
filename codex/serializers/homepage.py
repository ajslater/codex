"""Serializers for homepage endpoint."""

from rest_framework.serializers import IntegerField, Serializer


class HomepageSerializer(Serializer):
    """Minimal stats for homepage."""

    publisher_count = IntegerField()
    series_count = IntegerField()
    comic_count = IntegerField()
