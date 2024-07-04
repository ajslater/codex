"""Admin Flag View."""

from multiprocessing import cpu_count
from pathlib import Path
from platform import machine, python_version, release, system
from types import MappingProxyType

from caseconverter import snakecase
from django.contrib.sessions.models import Session
from django.db.models import Count

from codex.logger.logging import get_logger
from codex.models import (
    Comic,
    Library,
)
from codex.version import VERSION
from codex.views.const import CONFIG_MODELS, METADATA_MODELS, STATS_GROUP_MODELS
from codex.views.session import SessionView

LOG = get_logger(__name__)
_KEY_MODELS_MAP = MappingProxyType(
    {
        "config": CONFIG_MODELS,
        "groups": STATS_GROUP_MODELS,
        "metadata": METADATA_MODELS,
    }
)
_DOCKERENV_PATH = Path("/.dockerenv")
_CGROUP_PATH = Path("/proc/self/cgroup")
_USER_STATS = MappingProxyType(
    {
        SessionView.BROWSER_SESSION_KEY: ("top_group", "order_by", "dynamic_covers"),
        SessionView.READER_SESSION_KEY: (
            "finish_on_last_page",
            "fit_to",
            "reading_direction",
        ),
    }
)


class CodexStats:
    """Collect codex stats."""

    def __init__(self, params=None):
        """Specify which stats to collect. Default to all."""
        if not params:
            params = {}
        self.params = params

    @classmethod
    def _is_docker(cls):
        """Test if we're in a docker container."""
        try:
            return _DOCKERENV_PATH.is_file() or "docker" in _CGROUP_PATH.read_text()
        except Exception:
            return False

    def _get_models(self, key):
        """Get models from request params."""
        request_model_set = self.params.get(key, {})
        all_models = _KEY_MODELS_MAP[key]
        if request_model_set:
            models = []
            for model_name in request_model_set:
                for model in all_models:
                    if model.__name__.lower() == model_name.lower():
                        models.append(model)
        else:
            models = all_models
        return tuple(models)

    def _get_model_counts(self, key):
        """Get database counts of each model group."""
        models = self._get_models(key)
        obj = {}
        for model in models:
            name = snakecase(model.__name__) + "_count"
            qs = model.objects
            if model == Library:
                qs = qs.filter(covers_only=False)
            obj[name] = qs.count()
        return obj

    @staticmethod
    def _aggregate_session_key(session, session_key, session_subkeys, user_stats):
        session_dict = session.get(session_key, {})
        for key in session_subkeys:
            value = session_dict.get(key)
            if value is None:
                continue
            if key not in user_stats:
                user_stats[key] = {}
            if value not in user_stats[key]:
                user_stats[key][value] = 0
            user_stats[key][value] += 1

    @classmethod
    def _get_session_stats(cls):
        """Return the number of anonymous sessions."""
        sessions = Session.objects.all()
        anon_session_count = 0
        user_stats = {}
        for encoded_session in sessions:
            session = encoded_session.get_decoded()
            if not session.get("_auth_user_id"):
                anon_session_count += 1
            for session_key, subkeys in _USER_STATS.items():
                cls._aggregate_session_key(session, session_key, subkeys, user_stats)

        return user_stats, anon_session_count

    def _get_platform(self, obj):
        """Add dict of platform information to object."""
        platform = {
            "docker": self._is_docker(),
            "machine": machine(),
            "cores": cpu_count(),
            "system": {
                "name": system(),
                "release": release(),
            },
            "python_version": python_version(),
            "codex_version": VERSION,
        }
        obj["platform"] = platform

    def _get_config(self, obj):
        """Add dict of config informaation to object."""
        config = self._get_model_counts("config")
        sessions, config["user_anonymous_count"] = self._get_session_stats()
        config["user_registered_count"] = config.pop("users_count", 0)
        config["auth_group_count"] = config.pop("groups_count", 0)
        obj["config"] = config
        obj["sessions"] = sessions

    def _get_groups(self, obj):
        """Add dict of groups information to object."""
        groups = self._get_model_counts("groups")
        obj["groups"] = groups

    @staticmethod
    def _get_file_types(obj):
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
            file_types[name] = query_group["count"]
        obj["file_types"] = file_types

    def _get_metadata(self, obj):
        """Add dict of metadata counts to object."""
        metadata = self._get_model_counts("metadata")
        obj["metadata"] = metadata

    def get(self):
        """Construct the stats object."""
        obj = {}
        if not self.params or "platform" in self.params:
            self._get_platform(obj)
        if not self.params or "config" in self.params:
            self._get_config(obj)
        if not self.params or "groups" in self.params:
            self._get_groups(obj)
        if not self.params or "fileTypes" in self.params:
            self._get_file_types(obj)
        if not self.params or "metadata" in self.params:
            self._get_metadata(obj)
        return obj
