"""
List fetches take the admin's keys from the source registry.

``reading_list_credentials`` built comicbox's credentials by hand and gave
an object with empty keys when no key was set, where the registry's
``build_credentials`` gives None. comicbox reads both the same way: it
falls back to its config for a key the caller leaves unset.
"""

from comicbox.online_session import OnlineCredentials
from comicbox.readinglists.session import ReadingListSession
from comicbox.readinglists.sources import comicvine, metron
from django.test import TestCase

from codex.librarian.onlinetag.readinglists import reading_list_credentials
from codex.models import ComicboxTaggingDefaults
from codex.settings import COMICBOX_ONLINE_CONFIG


def _set_keys(**keys: str) -> None:
    fields = {"metron_key": "", "comicvine_key": "", "comicvine_url": ""}
    fields.update(keys)
    ComicboxTaggingDefaults.objects.update_or_create(pk=1, defaults=fields)


class ReadingListCredentialsTests(TestCase):
    """What a list fetch is handed, and what comicbox makes of it."""

    def test_no_defaults_row(self) -> None:
        ComicboxTaggingDefaults.objects.all().delete()
        assert reading_list_credentials() is None

    def test_no_key(self) -> None:
        _set_keys()
        assert reading_list_credentials() is None

    def test_each_key(self) -> None:
        _set_keys(metron_key="m", comicvine_key="c", comicvine_url="https://cv")
        credentials = reading_list_credentials()
        assert credentials is not None
        assert (
            credentials.metron_key,
            credentials.comicvine_key,
            credentials.comicvine_url,
        ) == ("m", "c", "https://cv")

    def test_comicbox_reads_none_as_empty_keys(self) -> None:
        """The old empty object and the new None resolve to the same auth."""
        for source in (metron, comicvine):
            with self.subTest(source=source.__name__):
                resolved = []
                for credentials in (None, OnlineCredentials()):
                    with ReadingListSession(
                        credentials=credentials, config=COMICBOX_ONLINE_CONFIG
                    ) as session:
                        resolved.append(source._credentials(session))  # noqa: SLF001
                assert resolved[0] == resolved[1]
