"""Group Mtimes."""

from rest_framework.serializers import CharField, Serializer

from codex.serializers.browser.settings import BrowserSettingsFilterSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.route import SimpleRouteSerializer


class GroupsMtimeSerializer(Serializer):
    """Groups Mtimes."""

    filters = BrowserSettingsFilterSerializer(required=False)
    q = CharField(allow_blank=True, required=False)
    groups = SimpleRouteSerializer(many=True, required=True)


class MtimeSerializer(Serializer):
    """Max mtime for all submitted groups."""

    max_mtime = TimestampField(read_only=True)
