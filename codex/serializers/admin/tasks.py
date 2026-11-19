"""Admin tasks serializers."""

from collections.abc import Iterator

from rest_framework.serializers import (
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.choices.jobs import ADMIN_JOBS


def _job_values() -> Iterator[str]:
    """Yield every task the Jobs tab posts: jobs, variants and aborts."""
    for group in ADMIN_JOBS["ADMIN_JOBS"]:
        if abort := group.get("abort"):
            yield abort
        for job in group["jobs"]:
            yield job["value"]
            if abort := job.get("abort"):
                yield abort
            yield from (variant["value"] for variant in job.get("variants", ()))


_ADMIN_JOB_CHOICES = tuple(sorted(set(_job_values())))


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=_ADMIN_JOB_CHOICES)
    library_id = IntegerField(required=False)
