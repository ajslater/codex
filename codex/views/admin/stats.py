"""Admin Flag View."""
from pathlib import Path
from platform import machine, python_version, release, system

from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from djangorestframework_camel_case.util import camel_to_underscore
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from codex.models import (
    Character,
    Comic,
    Credit,
    CreditPerson,
    CreditRole,
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
from codex.serializers.admin import AdminStatsSerializer
from codex.version import VERSION


class AdminStatsView(GenericAPIView):
    """Admin Flag Viewset."""

    permission_classes = [IsAdminUser]
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
        Credit,
        CreditPerson,
        CreditRole,
    )
    _CONFIG_MODELS = (
        Library,
        User,
        Group,
        Session,
    )
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

    @staticmethod
    def _get_model_counts(models):
        """Get database counts of each model group."""
        obj = {}
        for model in models:
            key = camel_to_underscore(model.__name__)
            key = key[1:] + "_count"
            obj[key] = model.objects.count()
        return obj

    @staticmethod
    def _get_anon_sessions():
        sessions = Session.objects.all()
        anon_sessions = 0
        for encoded_session in sessions:
            session = encoded_session.get_decoded()
            if not session.get("_auth_user_id"):
                anon_sessions += 1

        return anon_sessions

    @classmethod
    def get_object(cls):
        """Construct the stats object."""
        platform = {
            "docker": cls._is_docker(),
            "machine": machine(),
            "system": system(),
            "system_release": release(),
            "python": python_version(),
            "codex": VERSION,
        }

        config = cls._get_model_counts(cls._CONFIG_MODELS)
        config["session_anon_count"] = cls._get_anon_sessions()
        config["api_key"] = Timestamp.objects.get(name=Timestamp.API_KEY).version

        groups = cls._get_model_counts(cls._GROUP_MODELS)
        groups["pdf_count"] = pdf_count = Comic.objects.filter(
            file_format=Comic.FileFormat.PDF
        ).count()
        groups["comic_archive_count"] = groups["comic_count"] - pdf_count

        metadata = cls._get_model_counts(cls._METADATA_MODELS)

        obj = {
            "platform": platform,
            "config": config,
            "groups": groups,
            "metadata": metadata,
        }

        return obj

    def get(self, request, *args, **kwargs):
        """Get the stats object and serialize it."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
