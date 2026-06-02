"""Group Mtimes."""

from rest_framework.serializers import Serializer

from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.route import SimpleRouteSerializer


class CollectionsMtimeSerializer(BrowserFilterChoicesInputSerializer):
    """Groups Mtimes."""

    JSON_FIELDS = frozenset(
        BrowserFilterChoicesInputSerializer.JSON_FIELDS | {"collections"}
    )

    collections = SimpleRouteSerializer(many=True, required=True)


class MtimeSerializer(Serializer):
    """Max mtime for all submitted collections."""

    max_mtime = TimestampField(read_only=True)
