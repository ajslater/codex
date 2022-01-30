"""Admin view serializers."""
from rest_framework.serializers import CharField, Serializer


class QueueJobSerializer(Serializer):
    """Get tasks from front end."""

    task = CharField()
