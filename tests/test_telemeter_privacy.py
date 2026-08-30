"""
The anonymous stats payload must never carry private information.

Seeds a sentinel into every admin-authored string codex stores -- credentials,
urls, claim names, group names, banner text, api key, library paths -- and
asserts none of them reach the wire. Then walks the payload and requires every
leaf to be a number, a boolean, or a string drawn from a closed vocabulary.

If a new stat legitimately needs a new kind of string, add its vocabulary to
one of the ``_vocabularies`` sources deliberately. Do not widen the walk.
"""

import json
from typing import Final, override
from uuid import uuid4

from django.test import TestCase

from codex.choices.admin import AdminFlagChoices
from codex.collection import Collection
from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import (
    AdminFlag,
    ComicboxTaggingDefaults,
    EmailSettings,
    OIDCSettings,
)
from codex.models.identifier import Identifier, IdentifierSource, IdentifierType
from codex.models.library import Library

# Anything containing this must never appear in the payload.
SENTINEL: Final = "XXSENTINELXX"

# Keys whose values are free-form by nature and safe: version strings and the
# platform description, which carry no user or install identity.
_PLATFORM_KEYS: Final = frozenset(
    {"machine", "name", "release", "python_version", "codex_version"}
)

# The only payload dicts whose *keys* come from data rather than from code.
# Everywhere else a key is a field name chosen in codex's source, so checking
# it proves nothing. These are the ones that must stay closed-vocabulary.
_BUCKET_PATHS: Final = frozenset(
    {
        "stats.file_types",
        "stats.identifiers",
        "stats.usage.favorites",
        "stats.tagging.default_sources",
        "stats.sessions.top_collection",
        "stats.sessions.order_by",
        "stats.sessions.dynamic_covers",
        "stats.sessions.view_mode",
        "stats.sessions.table_cover_size",
        "stats.sessions.custom_covers",
        "stats.sessions.finish_on_last_page",
        "stats.sessions.fit_to",
        "stats.sessions.reading_direction",
        # per_user draws on the same closed vocabularies as sessions, counted
        # in users instead of rows. No vocabulary widening is needed: the
        # choices sources already cover every key, and _LITERALS covers the
        # "" that the live/global buckets carry for "never touched".
        "stats.per_user.browser_top_collection_users",
        "stats.per_user.browser_chosen_top_collection_users",
        "stats.per_user.browser_order_by_users",
        "stats.per_user.browser_chosen_order_by_users",
        "stats.per_user.browser_view_mode_users",
        "stats.per_user.browser_chosen_view_mode_users",
        "stats.per_user.browser_table_cover_size_users",
        "stats.per_user.browser_chosen_table_cover_size_users",
        "stats.per_user.browser_dynamic_covers_users",
        "stats.per_user.browser_chosen_dynamic_covers_users",
        "stats.per_user.browser_custom_covers_users",
        "stats.per_user.browser_chosen_custom_covers_users",
        "stats.per_user.reader_global_fit_to_users",
        "stats.per_user.reader_chosen_fit_to_users",
        "stats.per_user.reader_global_two_pages_users",
        "stats.per_user.reader_chosen_two_pages_users",
        "stats.per_user.reader_global_reading_direction_users",
        "stats.per_user.reader_chosen_reading_direction_users",
        "stats.per_user.reader_global_read_rtl_in_reverse_users",
        "stats.per_user.reader_chosen_read_rtl_in_reverse_users",
        "stats.per_user.reader_global_finish_on_last_page_users",
        "stats.per_user.reader_chosen_finish_on_last_page_users",
        "stats.per_user.reader_global_page_transition_users",
        "stats.per_user.reader_chosen_page_transition_users",
        "stats.per_user.reader_global_cache_book_users",
        "stats.per_user.reader_chosen_cache_book_users",
    }
)


# Strings the payload may carry that belong to no enum: the empty value, the
# collapsed-unknown buckets, and serialized booleans.
_LITERALS: Final = frozenset({"", "other", "true", "false", "unknown"})

# OIDC client authentication methods, a closed vocabulary from the spec.
_OIDC_AUTH_METHODS: Final = frozenset(
    {
        "client_secret_basic",
        "client_secret_post",
        "client_secret_jwt",
        "private_key_jwt",
        "none",
    }
)


def _enum_values(*enums) -> set[str]:
    """Every member value across the given enums."""
    return {member.value for enum in enums for member in enum}


def _choice_vocabularies() -> set[str]:
    """Collect the enums and choice tuples codex defines in its own source."""
    from codex.choices.browser import (
        BROWSER_ORDER_BY_CHOICES,
        BROWSER_TABLE_COVER_SIZE_CHOICES,
        BROWSER_VIEW_MODE_CHOICES,
    )
    from codex.choices.reader import READER_CHOICES
    from codex.models.choices import FileTypeChoices

    values = _enum_values(Collection, IdentifierType)
    values |= {value.lower() for value in _enum_values(FileTypeChoices)}
    values |= set(BROWSER_ORDER_BY_CHOICES)
    values |= set(BROWSER_VIEW_MODE_CHOICES)
    values |= set(BROWSER_TABLE_COVER_SIZE_CHOICES)
    return values | {
        value.lower() for choices in READER_CHOICES.values() for value in choices
    }


def _identifier_bucket_vocabulary() -> set[str]:
    """Cross the two closed vocabularies an "<source>:<id_type>" bucket key joins."""
    from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP

    sources = {source.value for source in ID_SOURCE_NAME_MAP} | {"other"}
    kinds = _enum_values(IdentifierType) | {"other"}
    return {f"{source}:{kind}" for source in sources for kind in kinds}


def _tagging_vocabularies() -> set[str]:
    """Tagging modes, plus the comicbox source names used as bucket keys."""
    from comicbox.formats.base.online import SOURCE_NAMES

    return set(SOURCE_NAMES) | _enum_values(
        ComicboxTaggingDefaults.MatchModeChoices,
        ComicboxTaggingDefaults.PromptsModeChoices,
    )


def _vocabularies() -> frozenset[str]:
    """Every closed vocabulary a payload string may be drawn from."""
    from codex.models.age_rating import AgeRatingMetron

    values = set(_LITERALS | _OIDC_AUTH_METHODS)
    values |= _choice_vocabularies()
    values |= _identifier_bucket_vocabulary()
    values |= _tagging_vocabularies()
    values |= set(AgeRatingMetron.objects.values_list("name", flat=True))
    return frozenset(values)


class TelemeterPrivacyTestCase(TestCase):
    """Assert the stats payload leaks nothing an administrator typed."""

    @override
    def setUp(self) -> None:
        from codex.startup import init_admin_flags, init_timestamps

        init_admin_flags()
        init_timestamps()
        self._seed_secrets()

    @staticmethod
    def _set_singleton(model, **fields) -> None:
        """Update the singleton row, which migrations may already have made."""
        row = model.objects.first() or model()
        for name, value in fields.items():
            setattr(row, name, value)
        row.save()

    @classmethod
    def _seed_secrets(cls) -> None:
        """Put a sentinel in every admin-authored string codex stores."""
        cls._set_singleton(
            ComicboxTaggingDefaults,
            metron_key=f"{SENTINEL}-metron-key",
            metron_user=f"{SENTINEL}-metron-user",
            metron_password=f"{SENTINEL}-metron-password",
            comicvine_key=f"{SENTINEL}-comicvine-key",
            comicvine_url=f"https://{SENTINEL}-comicvine.example.com",
            default_sources=["metron", f"{SENTINEL}-source"],
        )
        cls._set_singleton(
            OIDCSettings,
            enabled=True,
            provider_name=f"{SENTINEL}-provider",
            server_url=f"https://{SENTINEL}-idp.example.com",
            client_id=f"{SENTINEL}-client-id",
            client_secret=f"{SENTINEL}-client-secret",
            scope=f"openid {SENTINEL}-scope",
            username_claim=f"{SENTINEL}-claim",
            groups_claim=f"{SENTINEL}-groups",
            admin_group=f"{SENTINEL}-admins",
            token_auth_method=f"{SENTINEL}-auth-method",
        )
        cls._set_singleton(
            EmailSettings,
            host=f"smtp.{SENTINEL}.example.com",
            user=f"{SENTINEL}-smtp-user",
            password=f"{SENTINEL}-smtp-password",
            from_address=f"{SENTINEL}@example.com",
            subject_prefix=f"[{SENTINEL}] ",
        )
        AdminFlag.objects.filter(key=AdminFlagChoices.BANNER_TEXT.value).update(
            value=f"{SENTINEL}-banner"
        )
        AdminFlag.objects.filter(key=AdminFlagChoices.API_KEY.value).update(
            value=f"{SENTINEL}-api-key"
        )
        Library.objects.create(path=f"/{SENTINEL}-library", read_only=True)
        source = IdentifierSource.objects.create(name=f"{SENTINEL}-source")
        Identifier.objects.create(
            source=source,
            id_type=IdentifierType.ISSUE.value,
            key=f"{SENTINEL}-id",
            url=f"https://{SENTINEL}.example.com/1",
        )

    @staticmethod
    def _walk(node, path: str, leaves: list[tuple[str, object]]) -> None:
        """Collect every value, plus the keys of data-derived count buckets."""
        if isinstance(node, dict):
            in_bucket = path in _BUCKET_PATHS
            for key, value in node.items():
                if in_bucket:
                    leaves.append((f"{path}[key]", key))
                TelemeterPrivacyTestCase._walk(value, f"{path}.{key}", leaves)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                TelemeterPrivacyTestCase._walk(value, f"{path}[{index}]", leaves)
        else:
            leaves.append((path, node))

    def test_no_sentinel_in_payload(self) -> None:
        """No admin-authored string reaches the serialized payload."""
        payload = json.dumps(
            {"stats": CodexStats().get(), "uuid": str(uuid4())}, default=str
        )
        assert SENTINEL not in payload

    def test_unknown_identifier_source_collapsed(self) -> None:
        """A source name from a comic file is replaced by "other"."""
        identifiers = CodexStats().get()["identifiers"]
        assert identifiers
        for key in identifiers:
            assert SENTINEL not in key
        assert f"other:{IdentifierType.ISSUE.value}" in identifiers

    def test_every_leaf_is_a_number_bool_or_closed_vocabulary(self) -> None:
        """Walk the payload; no value may be an open-ended string."""
        vocabularies = {value.lower() for value in _vocabularies()}
        leaves: list[tuple[str, object]] = []
        self._walk(CodexStats().get(), "stats", leaves)
        assert leaves

        unexpected = []
        for path, value in leaves:
            if isinstance(value, bool | int | float) or value is None:
                continue
            if not isinstance(value, str):
                unexpected.append((path, value))
                continue
            if path.rsplit(".", 1)[-1] in _PLATFORM_KEYS:
                continue
            if value.lower() not in vocabularies:
                unexpected.append((path, value))
        assert not unexpected, f"open-ended strings in payload: {unexpected}"

    @staticmethod
    def _declared_field_names() -> frozenset[str]:
        """Every key name StatsSerializer declares, at any nesting depth."""
        from rest_framework.serializers import Serializer

        from codex.serializers.admin.stats import StatsSerializer

        names: set[str] = set()

        def walk(serializer) -> None:
            for name, field in serializer.get_fields().items():
                names.add(name)
                if isinstance(field, Serializer):
                    walk(field)

        walk(StatsSerializer())
        return frozenset(names)

    @classmethod
    def _undeclared_keys(cls, node, path: str, declared, found: list) -> None:
        """Collect dict keys that are neither declared fields nor bucket keys."""
        if not isinstance(node, dict):
            return
        if path in _BUCKET_PATHS:
            # Registered bucket: its keys are data, and the vocabulary walk
            # checks them.
            return
        for key, value in node.items():
            if key not in declared:
                found.append(f"{path}.{key}")
            cls._undeclared_keys(value, f"{path}.{key}", declared, found)

    def test_no_unregistered_data_keyed_bucket(self) -> None:
        """
        A count bucket missing from _BUCKET_PATHS is checked by nothing.

        Its keys never become leaf values, so the vocabulary walk skips them,
        and the sentinel test only seeds admin config -- not publisher, series
        or user rows. So instead of trusting _BUCKET_PATHS to describe itself,
        require every key in the payload to be either a field name declared in
        StatsSerializer or a key inside a registered bucket. A new bucket of
        library-sourced names satisfies neither.
        """
        declared = self._declared_field_names()
        found: list[str] = []
        self._undeclared_keys(CodexStats().get(), "stats", declared, found)
        assert not found, (
            "payload keys that are neither declared serializer fields nor "
            f"registered bucket keys: {sorted(found)}"
        )

    def test_the_bucket_check_catches_an_unregistered_bucket(self) -> None:
        """Prove the check above can actually fail."""
        payload = CodexStats().get()
        payload["usage"]["top_publishers"] = {"Marvel Comics": 10}
        found: list[str] = []
        self._undeclared_keys(payload, "stats", self._declared_field_names(), found)
        assert "stats.usage.top_publishers" in found
        assert "stats.usage.top_publishers.Marvel Comics" in found
