"""Group Mtimes."""

from rest_framework.serializers import Serializer

from codex.serializers.browser.settings import BrowserFilterChoicesInputSerilalizer
from codex.serializers.fields import TimestampField
from codex.serializers.route import SimpleRouteSerializer


class GroupsMtimeSerializer(BrowserFilterChoicesInputSerilalizer):
    """Groups Mtimes."""

    groups = SimpleRouteSerializer(many=True, required=True)


class MtimeSerializer(Serializer):
    """Max mtime for all submitted groups."""

    max_mtime = TimestampField(read_only=True)
