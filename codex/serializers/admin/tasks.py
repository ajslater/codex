"""Admin tasks serializers."""

from rest_framework.serializers import (
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.choices.admin import ADMIN_TASK_GROUPS

_ADMIN_TASK_CHOICES = tuple(
    sorted(
        item["value"]  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
        for group in ADMIN_TASK_GROUPS["tasks"]
        for item in group["tasks"]
    )
)


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=_ADMIN_TASK_CHOICES)
    library_id = IntegerField(required=False)
