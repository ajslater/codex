"""Admin Flag View."""

from multiprocessing import cpu_count
from pathlib import Path
from platform import machine, python_version, release, system
from types import MappingProxyType
from typing import Final

from caseconverter import snakecase
from django.contrib.sessions.models import Session
from django.db.models import Count

from codex.models import (
    Comic,
    Library,
)
from codex.models.settings import SettingsBrowser, SettingsReader
from codex.version import VERSION
from codex.views.const import CONFIG_MODELS, METADATA_MODELS, STATS_GROUP_MODELS

# Cap on per-call session decodes for the anonymous-session estimate.
# ``Session.get_decoded()`` runs HMAC + JSON parse per row; on installs
# with a long session history this dominates ``/admin/stats`` cold time.
# Telemetry is approximate by nature — a sample is enough.
_SESSION_SAMPLE_LIMIT: Final = 100

_KEY_MODELS_MAP = MappingProxyType(
    {
        "config": CONFIG_MODELS,
        "groups": STATS_GROUP_MODELS,
        "metadata": METADATA_MODELS,
    }
)
_DOCKERENV_PATH = Path("/.dockerenv")
_CGROUP_PATH = Path("/proc/self/cgroup")
_USER_STATS: Final = (
    (SettingsBrowser, ("top_group", "order_by", "dynamic_covers")),
    (SettingsReader, ("finish_on_last_page", "fit_to", "reading_direction")),
)


class CodexStats:
    """Collect codex stats."""

    def __init__(self, params=None) -> None:
        """Specify which stats to collect. Default to all."""
        if not params:
            params = {}
        self.params = params

    @classmethod
    def _is_docker(cls) -> bool:
        """Test if we're in a docker container."""
        try:
            return _DOCKERENV_PATH.is_file() or "docker" in _CGROUP_PATH.read_text()
        except Exception:
            return False

    def _get_models(self, key) -> tuple:
        """Get models from request params."""
        request_model_set = self.params.get(key, {})
        all_models = _KEY_MODELS_MAP[key]
        if request_model_set:
            models = [
                model
                for model in all_models
                for model_name in request_model_set
                if model.__name__.lower() == model_name.lower()
            ]
        else:
            models = all_models
        return tuple(models)

    def _get_model_counts(self, key) -> dict:
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
    def _estimate_anon_session_count() -> int:
        """
        Estimate anonymous-session count without decoding every row.

        ``Session.get_decoded()`` is HMAC + JSON parse per row, which
        dominates cold ``/admin/stats`` time on installs with history.
        Sample up to :data:`_SESSION_SAMPLE_LIMIT` rows, count how many
        lack ``_auth_user_id``, and scale by the total. Telemetry is
        approximate by nature.
        """
        total = Session.objects.count()
        if total == 0:
            return 0
        sample_qs = Session.objects.all()[:_SESSION_SAMPLE_LIMIT]
        sample_total = 0
        sample_anon = 0
        for encoded_session in sample_qs:
            sample_total += 1
            session = encoded_session.get_decoded()
            if not session.get("_auth_user_id"):
                sample_anon += 1
        if sample_total == 0:
            return 0
        return round(total * sample_anon / sample_total)

    @staticmethod
    def _aggregate_settings_field(model, field) -> dict:
        """Aggregate a single settings field via SQL GROUP BY."""
        rows = (
            model.objects.exclude(**{f"{field}__isnull": True})
            .values(field)
            .annotate(count=Count("pk"))
        )
        return {row[field]: row["count"] for row in rows}

    @classmethod
    def _get_session_stats(cls) -> tuple[dict, int]:
        """Return per-field user-settings buckets and anon session count."""
        user_stats: dict[str, dict] = {}
        for model, fields in _USER_STATS:
            for field in fields:
                bucket = cls._aggregate_settings_field(model, field)
                if bucket:
                    user_stats[field] = bucket
        return user_stats, cls._estimate_anon_session_count()

    def _add_platform(self, obj) -> None:
        """Add dict of platform information to object."""
        if self.params and "platform" not in self.params:
            return
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

    def _add_config(self, obj) -> None:
        """Add dict of config informaation to object."""
        if self.params and "config" not in self.params:
            return
        config = self._get_model_counts("config")
        sessions, config["user_anonymous_count"] = self._get_session_stats()
        config["user_registered_count"] = config.pop("users_count", 0)
        config["auth_group_count"] = config.pop("groups_count", 0)
        obj["config"] = config
        obj["sessions"] = sessions

    def _add_groups(self, obj) -> None:
        """Add dict of groups information to object."""
        if self.params and "groups" not in self.params:
            return
        groups = self._get_model_counts("groups")
        groups["issue_count"] = groups.pop("comic_count", 0)
        obj["groups"] = groups

    def _add_file_types(self, obj) -> None:
        """Query for file types."""
        if self.params and "file_types" not in self.params:
            return
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
        sorted_fts = dict(sorted(file_types.items()))
        obj["file_types"] = sorted_fts

    def _add_metadata(self, obj) -> None:
        """Add dict of metadata counts to object."""
        if self.params and "metadata" not in self.params:
            return
        metadata = self._get_model_counts("metadata")
        obj["metadata"] = metadata

    def get(self) -> dict:
        """Construct the stats object."""
        obj = {}
        self._add_platform(obj)
        self._add_config(obj)
        self._add_groups(obj)
        self._add_file_types(obj)
        self._add_metadata(obj)
        return obj
