"""Admin view serializers."""
from pathlib import Path

from django.contrib.auth.models import Group, User
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    ListField,
    ModelSerializer,
    Serializer,
    ValidationError,
)

from codex.models import AdminFlag, FailedImport, Library
from codex.serializers.choices import CHOICES
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class UserSerializer(ModelSerializer):
    """User Serializer."""

    class Meta:
        """Specify Model."""

        model = User
        fields = (
            "pk",
            "username",
            "groups",
            "is_staff",
            "is_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("pk", "last_login", "date_joined")


class UserChangePasswordSerializer(Serializer):
    """Special User Change Password Serializer."""

    password = CharField(write_only=True)


class GroupSerializer(ModelSerializer):
    """Group Serialier."""

    class Meta:
        """Specify Model."""

        model = Group
        fields = ("pk", "name", "library_set", "user_set")
        read_only_fields = ("pk",)


class AdminFlagSerializer(ModelSerializer):
    """Admin Flag Serializer."""

    class Meta:
        """Specify Model."""

        model = AdminFlag
        fields = ("pk", "name", "on")
        read_only_fields = ("name", "pk")


class LibrarySerializer(ModelSerializer):
    """Library Serializer."""

    class Meta:
        """Specify Model."""

        model = Library
        fields = ("pk", "events", "groups", "last_poll", "path", "poll", "poll_every")
        read_only_fields = ("last_poll", "pk")

    def validate_path(self, path):
        """Validate new library paths."""
        try:
            ppath = Path(path).resolve()
            if not ppath.is_dir():
                raise ValueError("Not a valid folder on this server")
            existing_paths = Library.objects.values_list("path", flat=True)
            for existing_path in existing_paths:
                existing_path = Path(existing_path)
                if existing_path.is_relative_to(ppath):
                    raise ValueError("Parent of existing library path")
                if ppath.is_relative_to(existing_path):
                    raise ValueError("Child of existing library path")
        except Exception as exc:
            LOG.error(exc)
            raise exc
        return str(ppath)


class FailedImportSerializer(ModelSerializer):
    """Failed Import Serializer."""

    class Meta:
        """Specify Model."""

        model = FailedImport
        fields = ("pk", "path", "created_at")
        read_only_fields = ("pk, " "path", "created_at")


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=CHOICES["admin_tasks"])
    library_id = IntegerField(required=False)


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
        try:
            path = Path(path)
            if not path.is_dir():
                raise ValidationError("Not a directory")
        except Exception as exc:
            raise ValidationError("Not a valid path") from exc
        return path

    def validate_show_hidden(self, show_hidden):
        """Snakecase the showHidden field."""
        return (
            show_hidden == "true"
            or self.initial_data.get("showHidden", False) == "true"
        )
