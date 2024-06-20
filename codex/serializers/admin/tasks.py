"""Admin tasks serializers."""

from rest_framework.serializers import (
    ChoiceField,
    IntegerField,
    Serializer,
)

from codex.serializers.choices import CHOICES


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=CHOICES["admin"]["tasks"])
    library_id = IntegerField(required=False)
