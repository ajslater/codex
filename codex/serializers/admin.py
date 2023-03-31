"""Admin view serializers."""
from pathlib import Path

from django.contrib.auth.models import Group, User
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DateTimeField,
    IntegerField,
    ListField,
    ModelSerializer,
    Serializer,
    ValidationError,
)

from codex.logger.logging import get_logger
from codex.models import AdminFlag, FailedImport, Library
from codex.serializers.choices import CHOICES

LOG = get_logger(__name__)


class UserSerializer(ModelSerializer):
    """User Serializer."""

    last_active = DateTimeField(read_only=True, allow_null=True)

    class Meta:
        """Specify Model."""

        model = User
        fields = (
            "pk",
            "username",
            "groups",
            "is_staff",
            "is_active",
            "last_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("pk", "last_active", "last_login", "date_joined")


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
        fields = ("key", "on")
        read_only_fields = ("key",)


class LibrarySerializer(ModelSerializer):
    """Library Serializer."""

    class Meta:
        """Specify Model."""

        model = Library
        fields = ("pk", "events", "groups", "last_poll", "path", "poll", "poll_every")
        read_only_fields = ("last_poll", "pk")

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


class FailedImportSerializer(ModelSerializer):
    """Failed Import Serializer."""

    class Meta:
        """Specify Model."""

        model = FailedImport
        fields = ("pk", "path", "created_at")
        read_only_fields = ("pk", "path", "created_at")


class AdminLibrarianTaskSerializer(Serializer):
    """Get tasks from front end."""

    task = ChoiceField(choices=CHOICES["admin"]["tasks"])
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
        ppath = Path(path)
        if not ppath.resolve().is_dir():
            reason = "Not a directory"
            raise ValidationError(reason)
        return path

    def validate_show_hidden(self, show_hidden):
        """Snakecase the showHidden field."""
        return (
            show_hidden == "true"
            or self.initial_data.get("showHidden", False) == "true"
        )


class AdminGroupSerializer(Serializer):
    """Group Counts."""

    publisher_count = IntegerField(required=False, read_only=True)
    imprint_count = IntegerField(required=False)
    series_count = IntegerField(required=False)
    volume_count = IntegerField(required=False)
    comic_count = IntegerField(required=False)
    folder_count = IntegerField(required=False)


class AdminFileTypeSerializer(Serializer):
    """File Type Counts."""

    pdf_count = IntegerField(required=False)
    cbz_count = IntegerField(required=False)
    cbr_count = IntegerField(required=False)
    cbt_count = IntegerField(required=False)
    unknown_count = IntegerField(required=False)


class AdminComicMetadataSerializer(Serializer):
    """Metadata Counts."""

    character_count = IntegerField(required=False)
    creator_count = IntegerField(required=False)
    creator_person_count = IntegerField(required=False)
    creator_role_count = IntegerField(required=False)
    genre_count = IntegerField(required=False)
    location_count = IntegerField(required=False)
    series_group_count = IntegerField(required=False)
    story_arc_count = IntegerField(required=False)
    tag_count = IntegerField(required=False)
    team_count = IntegerField(required=False)


class AdminConfigSerializer(Serializer):
    """Config Information."""

    library_count = IntegerField(required=False)
    user_count = IntegerField(required=False)
    group_count = IntegerField(required=False)
    session_count = IntegerField(required=False)
    session_anon_count = IntegerField(required=False)
    api_key = CharField(required=False)


class AdminPlatformSerializer(Serializer):
    """Platform Information."""

    docker = BooleanField()
    machine = CharField()
    system = CharField()
    system_release = CharField()
    python = CharField()
    codex = CharField()


class AdminStatsSerializer(Serializer):
    """Admin Stats Tab."""

    platform = AdminPlatformSerializer(required=False)
    config = AdminConfigSerializer(required=False)
    groups = AdminGroupSerializer(required=False)
    file_types = AdminFileTypeSerializer(required=False)
    metadata = AdminComicMetadataSerializer(required=False)


class APIKeySerializer(Serializer):
    """API Key."""

    api_key = CharField(source="name")
