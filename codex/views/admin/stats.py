"""Admin Flag View."""
from pathlib import Path
from platform import machine, python_version, release, system

from caseconverter import snakecase
from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.db.models import Count
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.models import (
    Character,
    Comic,
    Creator,
    CreatorPerson,
    CreatorRole,
    Folder,
    Genre,
    Imprint,
    Library,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
    Timestamp,
    Volume,
)
from codex.permissions import HasAPIKeyOrIsAdminUser
from codex.serializers.admin import AdminStatsSerializer
from codex.version import VERSION


class AdminStatsView(GenericAPIView):
    """Admin Flag Viewset."""

    permission_classes = [HasAPIKeyOrIsAdminUser]
    serializer_class = AdminStatsSerializer

    _GROUP_MODELS = (
        Publisher,
        Imprint,
        Series,
        Volume,
        Comic,
        Folder,
    )
    _METADATA_MODELS = (
        SeriesGroup,
        StoryArc,
        Location,
        Character,
        Team,
        Tag,
        Genre,
        Creator,
        CreatorPerson,
        CreatorRole,
    )
    _CONFIG_MODELS = (
        Library,
        User,
        Group,
        Session,
    )
    _KEY_MODELS_MAP = {
        "config": _CONFIG_MODELS,
        "groups": _GROUP_MODELS,
        "metadata": _METADATA_MODELS,
    }
    _DOCKERENV_PATH = Path("/.dockerenv")
    _CGROUP_PATH = Path("/proc/self/cgroup")

    @classmethod
    def _is_docker(cls):
        """Test if we're in a docker container."""
        try:
            return (
                cls._DOCKERENV_PATH.is_file()
                or "docker" in cls._CGROUP_PATH.read_text()
            )
        except Exception:
            return False

    def _get_request_counts(self, key):
        """Get lowercase names of requested fields."""
        request_count_list = self.request.GET.get(key, "")
        request_counts = set()
        for name in request_count_list.split(","):
            if name:
                request_counts.add(name.lower())
        return request_counts

    def _get_models(self, key):
        """Get models from request params."""
        request_model_list = self.request.GET.get(key)
        all_models = self._KEY_MODELS_MAP[key]
        if request_model_list:
            models = []
            for model_name in request_model_list.split(","):
                for model in all_models:
                    if model.__name__.lower() == model_name.lower():
                        models.append(model)
        else:
            models = all_models
        return models

    def _get_model_counts(self, key):
        """Get database counts of each model group."""
        models = self._get_models(key)
        obj = {}
        for model in models:
            model_name = snakecase(model.__name__)
            model_name += "_count"
            obj[model_name] = model.objects.count()
        return obj

    @staticmethod
    def _get_anon_sessions():
        """Return the number of anonymous sessions."""
        sessions = Session.objects.all()
        anon_sessions = 0
        for encoded_session in sessions:
            session = encoded_session.get_decoded()
            if not session.get("_auth_user_id"):
                anon_sessions += 1

        return anon_sessions

    def _get_platform(self, obj):
        """Add dict of platform information to object."""
        platform = {
            "docker": self._is_docker(),
            "machine": machine(),
            "system": system(),
            "system_release": release(),
            "python": python_version(),
            "codex": VERSION,
        }
        obj["platform"] = platform

    def _get_config(self, obj):
        """Add dict of config informaation to object."""
        config = self._get_model_counts("config")
        request_counts = self._get_request_counts("config")
        if not request_counts or "sessionanon" in request_counts:
            config["session_anon_count"] = self._get_anon_sessions()
        if not request_counts or "apikey" in request_counts:
            config["api_key"] = Timestamp.objects.get(
                key=Timestamp.TimestampChoices.API_KEY.value
            ).version
        obj["config"] = config

    def _get_file_types(self):
        """Query for file types."""
        file_types = {}
        qs = (
            Comic.objects.values("file_type")
            .annotate(count=Count("file_type"))
            .order_by()
        )
        for query_group in qs:
            value = query_group["file_type"]
            name = value.lower() if value else "unknown"
            field = f"{name}_count"
            file_types[field] = query_group["count"]
        return file_types

    def _get_groups(self, obj):
        """Add dict of groups information to object."""
        if not self.params or "groups" in self.params:
            groups = self._get_model_counts("groups")
            obj["groups"] = groups

        if not self.params or "fileTypes" in self.params:
            file_types = self._get_file_types()
            obj["file_types"] = file_types

    def _get_metadata(self, obj):
        """Add dict of metadata counts to object."""
        metadata = self._get_model_counts("metadata")
        obj["metadata"] = metadata

    def get_object(self):
        """Construct the stats object."""
        obj = {}
        if not self.params or "platform" in self.params:
            self._get_platform(obj)
        if not self.params or "config" in self.params:
            self._get_config(obj)
        if not self.params or "groups" in self.params:
            self._get_groups(obj)
        if not self.params or "metadata" in self.params:
            self._get_metadata(obj)
        return obj

    def get(self, *args, **kwargs):
        """Get the stats object and serialize it."""
        params = self.request.GET.get("params")
        if params:
            self.params = set(params.split(","))
        else:
            self.params = None

        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
