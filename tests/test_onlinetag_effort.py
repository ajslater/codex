"""
The online-tag effort setting, from the admin default to the session.

Effort bounds how many requests a comic may spend against a source that
fans out per candidate, which today means Comic Vine alone. It is not an
``OnlineSession`` keyword: it lives in the settings tree the session
layers its own preferences over, so codex hands those settings over.

Match mode is the knob it is most often confused with. Match mode decides
how a verdict is applied once the calls are already spent, and changes no
request count at all.
"""

from comicbox.config.online import Effort, resolve_effort
from django.test import SimpleTestCase

from codex.librarian.onlinetag.session_manager import _online_config
from codex.models.admin import ComicboxTaggingDefaults
from codex.settings import COMICBOX_CACHE_PATH
from codex.views.admin.onlinetag import AdminOnlineTagStartView


class OnlineConfigEffortTestCase(SimpleTestCase):
    """The settings a session is handed carry the scan's effort."""

    def test_effort_reaches_the_session_settings(self) -> None:
        """Each named effort lands in the tuning the session layers over."""
        for effort in Effort:
            config = _online_config(effort.value)
            assert config.online.tuning.effort is effort

    def test_an_unset_effort_is_left_unset(self) -> None:
        """
        Spelling out the value it resolves to would change its meaning.

        Comicbox tells "nobody chose" from "someone chose balanced", and
        only the first lets it spare a large run.
        """
        config = _online_config("")

        assert config.online.tuning.effort is None
        assert resolve_effort(config.online, "comicvine") is Effort.BALANCED

    def test_the_rest_of_codexs_online_settings_survive(self) -> None:
        """
        Applying an effort must not drop the cache directory.

        The directory is the whole reason codex hands settings over; a
        rebuild that lost it would send comicbox's caches back to a
        location a container recreation throws away.
        """
        config = _online_config(Effort.THOROUGH.value)
        assert config.online.cache.dir == COMICBOX_CACHE_PATH
        assert not config.general.delete_keys


class ResolveEffortTestCase(SimpleTestCase):
    """What a scan runs at, given a request and an admin default."""

    @staticmethod
    def _resolve(requested: str | None, default: str | None) -> str:
        # Unsaved: the resolver only reads the one field.
        defaults = (
            ComicboxTaggingDefaults(default_effort=default)
            if default is not None
            else None
        )
        return AdminOnlineTagStartView._resolve_effort(  # noqa: SLF001
            {"effort": requested}, defaults
        )

    def test_the_request_wins(self) -> None:
        """A scan may ask for something other than the admin default."""
        assert self._resolve("thorough", "minimal") == "thorough"

    def test_the_admin_default_fills_in(self) -> None:
        """A scan that asks for nothing runs at the configured default."""
        assert self._resolve(None, "minimal") == "minimal"

    def test_nothing_chosen_pins_nothing(self) -> None:
        """
        A fresh install names no effort.

        Naming none is not the same as naming the one it resolves to.
        Comicbox reads a named effort as a decision to leave alone, so
        only while none is named can it spend less on a run large enough
        to otherwise stretch into hours of Comic Vine rate limiting.
        """
        assert self._resolve(None, None) == ""
        assert self._resolve(None, "") == ""

    def test_the_choices_mirror_comicboxs_enum(self) -> None:
        """A value codex offers has to be one comicbox accepts."""
        codex_values = [
            choice.value
            for choice in ComicboxTaggingDefaults.EffortChoices
            if choice.value
        ]
        assert codex_values == [effort.value for effort in Effort]

    def test_unset_is_offered_and_is_the_default(self) -> None:
        """The choice that leaves the decision to comicbox."""
        choices = ComicboxTaggingDefaults.EffortChoices
        field = ComicboxTaggingDefaults._meta.get_field("default_effort")

        assert choices.AUTO.value == ""
        assert field.default == choices.AUTO
