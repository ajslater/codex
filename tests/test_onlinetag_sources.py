"""
The online-tag source registry, and what a source codex never registered does.

Codex drives only the sources registered in ``codex.librarian.onlinetag.sources``.
comicbox can know more: comicbox 5.7 adds ``versedb`` to ``SOURCE_NAMES``
before codex can drive it. Such a source must be inert everywhere codex takes
a source name: refused with a 400 or a user-facing message, never a 500, and
never handed another source's key. ``_UNREGISTERED`` names it. These tests
hold on any comicbox, because codex has to refuse that name whether comicbox
knows it or not; the registry's own filtering is tested on a made-up
comicbox vocabulary.
"""

import json
from http import HTTPStatus
from importlib import import_module
from typing import Any, Final, override
from unittest.mock import patch

import pytest
from comicbox.config.online import Effort
from comicbox.config.online.settings import OnlineSourceCredentials
from comicbox.formats.base.online import SOURCE_NAMES
from comicbox.formats.base.online.sources.base import OnlineSource
from comicbox.formats.comicvine_api.online_source import ComicVineOnlineSource
from comicbox.formats.metron_api.online_source import MetronOnlineSource
from comicbox.online_estimate import requests_per_comic
from comicbox.online_session import OnlineCredentials
from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase

from codex.choices.admin import TAGGING_CHOICES
from codex.choices.onlinetag import TAGGING_ESTIMATE
from codex.librarian.onlinetag.credential_validator import (
    KNOWN_SOURCES,
    validate_credentials,
)
from codex.librarian.onlinetag.sources import (
    CREDENTIAL_FIELDS,
    SOURCES,
    SUPPORTED_SOURCES,
    configured_sources,
    source_credentials,
    supported_sources,
)
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import OnlineTagStartSerializer
from codex.views.admin.identifier_parse import parse_identifier_input

#: A source comicbox may know (comicbox 5.7 does) that codex has not registered.
_UNREGISTERED: Final = "versedb"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_DEFAULTS_URL: Final = "/api/v4/admin/tagging-defaults"
_VALIDATE_URL: Final = f"{_DEFAULTS_URL}/validate"
_START_URL: Final = "/api/v4/admin/tag-sessions/start"
_COMICVINE_PER_HOUR: Final = 200
_FULL_CREDS: Final = OnlineCredentials(
    metron_key="m", comicvine_key="c", comicvine_url="https://cv.example.com/api"
)


class RegistryTests(SimpleTestCase):
    """The registry filters comicbox's names and describes each source."""

    def test_an_unregistered_comicbox_source_is_filtered_out(self) -> None:
        names = ("metron", "comicvine", _UNREGISTERED)
        assert supported_sources(names) == ("metron", "comicvine")

    def test_comicbox_order_is_kept(self) -> None:
        names = ("comicvine", _UNREGISTERED, "metron")
        assert supported_sources(names) == ("comicvine", "metron")

    def test_supported_sources_derive_from_comicbox(self) -> None:
        assert supported_sources(SOURCE_NAMES) == SUPPORTED_SOURCES
        assert SUPPORTED_SOURCES == ("metron", "comicvine")
        assert tuple(SOURCES) == SUPPORTED_SOURCES
        assert frozenset(SUPPORTED_SOURCES) == KNOWN_SOURCES

    def test_credential_fields_exist_on_both_ends(self) -> None:
        """Each field is a model column and a comicbox credential of one name."""
        assert CREDENTIAL_FIELDS == ("metron_key", "comicvine_key", "comicvine_url")
        for field in CREDENTIAL_FIELDS:
            ComicboxTaggingDefaults._meta.get_field(field)
            assert field in OnlineCredentials.__dataclass_fields__

    def test_each_source_names_its_comicbox_class_and_module(self) -> None:
        classes = {name: source.source_class() for name, source in SOURCES.items()}
        assert classes == {
            "metron": MetronOnlineSource,
            "comicvine": ComicVineOnlineSource,
        }
        for source in SOURCES.values():
            assert issubclass(source.source_class(), OnlineSource)
            assert callable(import_module(source.module).close_shared_sessions)

    def test_labels_are_comicbox_display_names(self) -> None:
        labels = [source.label for source in SOURCES.values()]
        assert labels == ["Metron", "Comic Vine"]


class SourceCredentialsTests(SimpleTestCase):
    """Each source gets its own slice of the credentials, and only that."""

    def test_metron_takes_its_key_and_no_url(self) -> None:
        creds = OnlineCredentials(metron_key="m", metron_url="https://x.example")
        assert source_credentials("metron", creds) == OnlineSourceCredentials(key="m")

    def test_comicvine_takes_its_key_and_url(self) -> None:
        assert source_credentials("comicvine", _FULL_CREDS) == (
            OnlineSourceCredentials(key="c", url="https://cv.example.com/api")
        )

    def test_blank_values_are_unset(self) -> None:
        creds = OnlineCredentials(comicvine_key="", comicvine_url="")
        assert source_credentials("comicvine", creds) == OnlineSourceCredentials()

    def test_an_unregistered_source_gets_no_one_elses_key(self) -> None:
        """Before the registry, any non-Metron source got Comic Vine's key."""
        assert source_credentials(_UNREGISTERED, _FULL_CREDS) == (
            OnlineSourceCredentials()
        )

    def test_configured_sources_reads_comicbox_credentials(self) -> None:
        assert configured_sources(_FULL_CREDS) == ("metron", "comicvine")
        assert configured_sources(OnlineCredentials(comicvine_key="c")) == (
            "comicvine",
        )

    def test_a_url_alone_configures_nothing(self) -> None:
        creds = OnlineCredentials(comicvine_url="https://cv.example.com/api")
        assert configured_sources(creds) == ()

    def test_no_holder_configures_nothing(self) -> None:
        assert configured_sources(None) == ()


class UnregisteredSourceDefaultsTests(SimpleTestCase):
    """Nothing defaults to every name comicbox knows."""

    def test_the_frontend_is_offered_the_supported_sources(self) -> None:
        assert TAGGING_CHOICES["sources"] == SUPPORTED_SOURCES

    def test_a_start_request_without_sources_uses_the_supported_ones(self) -> None:
        serializer = OnlineTagStartSerializer(data={"collection": "c", "pks": ["1"]})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["sources"] == list(SUPPORTED_SOURCES)

    def test_a_task_defaults_to_the_supported_sources(self) -> None:
        task = BulkOnlineTagTask(comic_pks=frozenset({1}), session_id="s")
        assert task.sources == SUPPORTED_SOURCES

    def test_validating_an_unregistered_source_is_a_no_op(self) -> None:
        assert validate_credentials(_FULL_CREDS, {_UNREGISTERED}) == {}


class UnregisteredSourceIdentifierTests(SimpleTestCase):
    """Tag-by-id refuses an unregistered source with a message, not a crash."""

    def test_its_prefix_is_an_unknown_source(self) -> None:
        with pytest.raises(ValueError, match="Unknown source") as exc_info:
            parse_identifier_input(f"{_UNREGISTERED}:123")
        assert str(exc_info.value).endswith("Use metron or comicvine.")

    def test_its_url_is_refused(self) -> None:
        # comicbox 5.7 parses the domain and codex says the source isn't
        # supported; an older comicbox doesn't know the domain, so the url
        # falls through to an unknown ``https:`` prefix. Either way the
        # operator is told which sources codex takes.
        with pytest.raises(ValueError, match=r"(?i)metron"):
            parse_identifier_input("https://versedb.com/issue/1215061/some-issue")


def _make_admin() -> User:
    return User.objects.create_user(
        username="onlinetag_sources_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class UnregisteredSourceEndpointTests(TestCase):
    """The admin endpoints refuse an unregistered source with a 400."""

    @override
    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(_make_admin())
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "m", "comicvine_key": "c"}
        )

    def _post(self, url: str, data: dict):
        return self.client.post(url, data=data, content_type="application/json")

    def test_validating_every_source_probes_only_the_registered_ones(self) -> None:
        """With no ``source`` this was a ``KeyError`` once comicbox knew more."""
        with (
            patch.object(MetronOnlineSource, "probe", return_value=None),
            patch.object(ComicVineOnlineSource, "probe", return_value=None),
        ):
            response = self._post(_VALIDATE_URL, {})
        assert response.status_code == HTTPStatus.OK, response.content
        results = response.json()["data"]["results"]
        assert set(results) == {"metron", "comicvine"}
        assert all(result["ok"] for result in results.values())

    def test_validating_an_unregistered_source_is_a_400(self) -> None:
        response = self._post(_VALIDATE_URL, {"source": _UNREGISTERED})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_an_unregistered_default_source_is_a_400(self) -> None:
        response = self.client.put(
            _DEFAULTS_URL,
            data=json.dumps({"defaultSources": ["metron", _UNREGISTERED]}),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert _UNREGISTERED not in defaults.default_sources

    def test_starting_a_scan_with_an_unregistered_source_is_a_400(self) -> None:
        response = self._post(
            _START_URL,
            {"collection": "comics", "pks": ["1"], "sources": [_UNREGISTERED]},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_pinning_an_unregistered_source_is_a_400(self) -> None:
        response = self._post(
            _START_URL,
            {"collection": "comics", "pks": ["1"], "ids": {_UNREGISTERED: "123"}},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST


class ConfiguredSourcesFieldTests(TestCase):
    """The tagging defaults report which supported sources have a key."""

    @override
    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(_make_admin())

    def _configured(self, **fields: str) -> list[str]:
        unset = dict.fromkeys(CREDENTIAL_FIELDS, "")
        ComicboxTaggingDefaults.objects.filter(pk=1).update(**(unset | fields))
        response = self.client.get(_DEFAULTS_URL)
        assert response.status_code == HTTPStatus.OK, response.content
        return response.json()["data"]["configuredSources"]

    def test_none(self) -> None:
        assert self._configured() == []

    def test_one(self) -> None:
        assert self._configured(comicvine_key="c") == ["comicvine"]

    def test_two_in_priority_order(self) -> None:
        assert self._configured(comicvine_key="c", metron_key="m") == [
            "metron",
            "comicvine",
        ]

    def test_a_url_alone_is_not_configured(self) -> None:
        assert self._configured(comicvine_url="https://cv.example.com/api") == []


def _estimate(key: str) -> Any:
    """One entry of the estimate table; its values differ in type by key."""
    return TAGGING_ESTIMATE[key]


class TaggingEstimateTests(SimpleTestCase):
    """The launcher's estimate table is comicbox's, per source and effort."""

    def test_requests_per_comic_is_comicbox_pricing(self) -> None:
        table = _estimate("requests_per_comic")
        assert tuple(table) == SUPPORTED_SOURCES
        for source in SUPPORTED_SOURCES:
            assert dict(table[source]) == {
                effort.value: requests_per_comic(source, effort.value)
                for effort in Effort
            }

    def test_source_rates(self) -> None:
        rates = _estimate("source_rates")
        assert tuple(rates) == SUPPORTED_SOURCES
        metron = rates["metron"]
        assert metron["per_hour"] == metron["per_minute"] * 60
        assert rates["comicvine"]["per_hour"] == _COMICVINE_PER_HOUR
