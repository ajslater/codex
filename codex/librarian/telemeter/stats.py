"""Admin Flag View."""

from multiprocessing import cpu_count
from platform import machine, python_version, release, system
from types import MappingProxyType
from typing import Any, Final

from caseconverter import snakecase
from django.contrib.sessions.models import Session
from django.db.models import Count

from codex.librarian.telemeter.admin_stats import (
    get_admin_flag_stats,
    get_auth_stats,
    get_deployment_stats,
    get_email_stats,
    get_tagging_stats,
    get_throttle_stats,
)
from codex.librarian.telemeter.count_stats import (
    get_comic_populated_stats,
    get_identifier_stats,
    get_library_stats,
    get_multi_sort_count,
    get_usage_stats,
)
from codex.librarian.telemeter.per_user_stats import get_per_user_stats
from codex.models import (
    Comic,
)
from codex.models.settings import SettingsBrowser, SettingsReader
from codex.util import is_docker
from codex.version import VERSION
from codex.views.const import (
    CONFIG_MODELS,
    METADATA_MODELS,
    STATS_COLLECTION_MODELS,
    STATS_USAGE_MODELS,
)

# Cap on per-call session decodes for the anonymous-session estimate.
# ``Session.get_decoded()`` runs HMAC + JSON parse per row; on installs
# with a long session history this dominates ``/admin/stats`` cold time.
# Telemetry is approximate by nature — a sample is enough.
_SESSION_SAMPLE_LIMIT: Final = 100

_KEY_MODELS_MAP = MappingProxyType(
    {
        "config": CONFIG_MODELS,
        "collections": STATS_COLLECTION_MODELS,
        "metadata": METADATA_MODELS,
        "usage": STATS_USAGE_MODELS,
    }
)
_USER_STATS: Final = (
    (
        SettingsBrowser,
        (
            "top_collection",
            "order_by",
            "dynamic_covers",
            "view_mode",
            "table_cover_size",
            "custom_covers",
        ),
    ),
    (SettingsReader, ("finish_on_last_page", "fit_to", "reading_direction")),
)
# Sections built by a single collector function, in payload order.
_SIMPLE_SECTIONS: Final = (
    ("identifiers", get_identifier_stats),
    ("admin_flags", get_admin_flag_stats),
    ("tagging", get_tagging_stats),
    ("auth", get_auth_stats),
    ("email", get_email_stats),
    ("throttle", get_throttle_stats),
    ("deployment", get_deployment_stats),
    # Last, so EXPECTED_SECTIONS stays append-only. Named per_user rather than
    # user_settings: the admin stats tab already has a "User Settings" table
    # rendering the unrelated ``sessions`` section.
    ("per_user", get_per_user_stats),
)


class CodexStats:
    """Collect codex stats."""

    def __init__(self, params=None) -> None:
        """Specify which stats to collect. Default to all."""
        if not params:
            params = {}
        self.params = params

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
            obj[name] = model.objects.count()
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
        user_stats: dict[str, Any] = {}
        for model, fields in _USER_STATS:
            for field in fields:
                bucket = cls._aggregate_settings_field(model, field)
                if bucket:
                    user_stats[field] = bucket
        user_stats["multi_sort_count"] = get_multi_sort_count()
        return user_stats, cls._estimate_anon_session_count()

    def _add_platform(self, obj) -> None:
        """Add dict of platform information to object."""
        if self.params and "platform" not in self.params:
            return
        platform = {
            "docker": is_docker(),
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
        # ``_get_model_counts`` keys off ``snakecase(model.__name__) + "_count"``
        # — for ``django.contrib.auth.models.User`` / ``Group`` that is
        # ``user_count`` / ``group_count`` (singular). The previous pop()s
        # used ``users_count`` / ``groups_count`` which never existed,
        # so both fields silently fell back to the default ``0``.
        config["user_registered_count"] = config.pop("user_count", 0)
        config["auth_group_count"] = config.pop("group_count", 0)
        config.update(get_library_stats())
        obj["config"] = config
        obj["sessions"] = sessions

    def _add_collections(self, obj) -> None:
        """Add dict of collections information to object."""
        if self.params and "collections" not in self.params:
            return
        collections = self._get_model_counts("collections")
        collections["issue_count"] = collections.pop("comic_count", 0)
        obj["collections"] = collections

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
        metadata.update(get_comic_populated_stats())
        obj["metadata"] = metadata

    def _add_usage(self, obj) -> None:
        """Add dict of reader engagement counts to object."""
        if self.params and "usage" not in self.params:
            return
        obj["usage"] = get_usage_stats()

    def _add_simple_sections(self, obj) -> None:
        """Add every section that one collector builds on its own."""
        for key, collector in _SIMPLE_SECTIONS:
            if self.params and key not in self.params:
                continue
            obj[key] = collector()

    def get(self) -> dict:
        """Construct the stats object."""
        obj = {}
        self._add_platform(obj)
        self._add_config(obj)
        self._add_collections(obj)
        self._add_file_types(obj)
        self._add_metadata(obj)
        self._add_usage(obj)
        self._add_simple_sections(obj)
        return obj
