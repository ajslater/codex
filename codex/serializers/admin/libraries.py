"""Admin libraries serializers."""

from pathlib import Path

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.models import FailedImport, Library
from codex.serializers.models.base import BaseModelSerializer


class LibrarySerializer(BaseModelSerializer):
    """Library Serializer."""

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = Library
        fields = (
            "pk",
            "path",
            "events",
            "last_poll",
            "poll",
            "poll_every",
            "groups",
            "covers_only",
        )
        read_only_fields = ("last_poll", "pk", "covers_only")

    def validate_path(self, path):
        """Validate new library paths."""
        ppath = Path(path).resolve()
        if not ppath.is_dir():
            reason = "Not a valid folder on this server"
            raise ValidationError(reason)
        existing_path_strs = Library.objects.values_list("path", flat=True)
        for existing_path_str in existing_path_strs:
            existing_path = Path(existing_path_str)
            if existing_path.is_relative_to(ppath):
                reason = "Parent of existing library path"
                raise ValidationError(reason)
            if ppath.is_relative_to(existing_path):
                reason = "Child of existing library path"
                raise ValidationError(reason)
        return path


class FailedImportSerializer(BaseModelSerializer):
    """Failed Import Serializer."""

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = FailedImport
        fields = ("pk", "path", "created_at")
        read_only_fields = ("pk", "path", "created_at")


class AdminFolderListSerializer(Serializer):
    """Get a list of dirs."""

    root_folder = CharField(read_only=True)
    folders = ListField(child=CharField(read_only=True))


class AdminFolderSerializer(Serializer):
    """Validate a dir."""

    path = CharField(default=".")
    show_hidden = BooleanField(default=False)

    def validate_path(self, path):
        """Validate the path is an existing directory."""
        ppath = Path(path)
        if not ppath.resolve().is_dir():
            reason = "Not a directory"
            raise ValidationError(reason)
        return path

    def validate_show_hidden(self, show_hidden):
        """Snakecase the showHidden field."""
        return (
            show_hidden == "true" or self.initial_data.get("showHidden") == "true"  # type: ignore
        )
