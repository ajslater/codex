"""Admin tasks serializers."""

from rest_framework.serializers import (
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.choices import ADMIN_TASKS


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=ADMIN_TASKS)
    library_id = IntegerField(required=False)
