"""
Unit tests for the credentials the session manager hands comicbox.

``_build_credentials`` reads the singleton tagging defaults; a source counts as
configured only when it carries something that can actually authenticate.
"""

from codex.models import ComicboxTaggingDefaults
from tests.onlinetag_session_fakes import OnlineTagSessionTestCase


class OnlineTagCredentialsTests(OnlineTagSessionTestCase):
    """A key configures a source; a bare url does not."""

    def test_a_metron_key_configures_metron(self) -> None:
        manager = self.manager
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t"}
        )
        keyed = manager._build_credentials()  # noqa: SLF001
        assert keyed is not None
        assert keyed.metron_key == "t"
        assert manager._source_has_credentials(keyed, "metron") is True  # noqa: SLF001

    def test_no_metron_credentials_at_all_is_unconfigured(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "metron_key": "",
                "comicvine_key": "",
            },
        )
        assert self.manager._build_credentials() is None  # noqa: SLF001

    def test_comicvine_custom_url_reaches_comicbox(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "comicvine_key": "key",
                "comicvine_url": "https://cv.example.com/api",
            },
        )
        credentials = self.manager._build_credentials()  # noqa: SLF001
        assert credentials is not None
        assert credentials.comicvine_url == "https://cv.example.com/api"

    def test_a_custom_url_alone_is_not_credentials(self) -> None:
        """A url cannot authenticate, so it must not configure the source."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "metron_key": "",
                "comicvine_key": "",
                "comicvine_url": "https://cv.example.com/api",
            },
        )
        assert self.manager._build_credentials() is None  # noqa: SLF001
