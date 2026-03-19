"""Admin tasks serializers."""

from rest_framework.serializers import (
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.choices.jobs import ADMIN_JOBS

_ADMIN_JOB_CHOICES = tuple(
    sorted(
        {item["value"] for group in ADMIN_JOBS["ADMIN_JOBS"] for item in group["jobs"]}
        | {
            variant["value"]
            for group in ADMIN_JOBS["ADMIN_JOBS"]
            for item in group["jobs"]
            for variant in item.get("variants", ())
        }
    )
)


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=_ADMIN_JOB_CHOICES)
    library_id = IntegerField(required=False)
