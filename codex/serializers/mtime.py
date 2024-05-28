"""Group Mtimes."""

from rest_framework.serializers import BooleanField, Serializer

from codex.serializers.fields import IntListField, TimestampField


class GroupMtimeSerializer(Serializer):
    """Group Mtimes."""

    pks = IntListField(read_only=True)
    mtime = TimestampField(read_only=True)


class GroupsMtimeSerializer(Serializer):
    """Groups Mtimes."""

    groups = GroupMtimeSerializer(many=True)
    use_bookmark_filter = BooleanField(read_only=True)


class MtimeSerializer(Serializer):
    """Max mtime for all submitted groups."""

    max_mtime = TimestampField(read_only=True)
