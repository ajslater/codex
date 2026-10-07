"""Admin doctor report serializers."""

from rest_framework.serializers import (
    CharField,
    IntegerField,
    ListField,
    Serializer,
)


class DoctorRowSerializer(Serializer):
    """One row of comicbox's doctor report."""

    section = CharField(read_only=True)
    name = CharField(read_only=True)
    #: OK, WARN, OFF, MISSING, WRONG VERSION, MISCONFIGURED or ERROR.
    status = CharField(read_only=True)
    found = CharField(read_only=True)
    detail = CharField(read_only=True)
    fix = CharField(read_only=True)


class DoctorReportSerializer(Serializer):
    """comicbox's doctor report for this install."""

    #: comicbox version, Python, platform, and "Docker" inside a container.
    header = ListField(child=CharField(), read_only=True)
    results = DoctorRowSerializer(many=True, read_only=True)
    problems = IntegerField(read_only=True)
