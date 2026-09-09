"""Collection Mtimes."""

from rest_framework.serializers import Serializer

from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.fields.collection import MtimeCollectionField
from codex.serializers.route import SimpleRouteSerializer


class MtimeRouteSerializer(SimpleRouteSerializer):
    """A route the mtime probe accepts, including reader-only arcs."""

    collection = MtimeCollectionField()


class CollectionsMtimeSerializer(BrowserFilterChoicesInputSerializer):
    """Collections Mtimes."""

    JSON_FIELDS = frozenset(
        BrowserFilterChoicesInputSerializer.JSON_FIELDS | {"collections"}
    )

    collections = MtimeRouteSerializer(many=True, required=True)


class MtimeSerializer(Serializer):
    """Max mtime for all submitted collections."""

    max_mtime = TimestampField(read_only=True)
